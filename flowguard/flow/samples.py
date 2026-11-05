"""Opaque saved-file inputs, reduced to actual abstract starts inside the core worker.

File formats belong to the SUT. Native execution and comparison keep their existing
owners; callbacks only produce existing input recipes and project captured graphs.
"""
from __future__ import annotations

import base64
import copy
from dataclasses import dataclass,replace
import hashlib
import itertools
import json
import os
from pathlib import Path
import types

from ..export import to_jsonable
from ..native import session
from ..native.capture import plain
from ..native.inputs import directory_stamp,file_stamp
from ..map.common import matches_any
from .checks import CONFLICT,check_model,make_finding
from .explore import Bounds,_has_id
from .model import Ids,ModelError,Rule,SettingValues,load_model


@dataclass(frozen=True)
class SampleSource:
    paths: object
    version: str
    load: object
    state: object
    dispatch: object = None
    source: str | None = None
    line: int | None = None

    def __post_init__(self):
        paths=(self.paths,) if isinstance(self.paths,str) else tuple(self.paths)
        if not paths or any(type(path) is not str or not path for path in paths):
            raise ModelError('saved samples need explicit file paths or glob patterns')
        if type(self.version) is not str or not self.version.strip():
            raise ModelError('saved samples need a source version label')
        if not callable(self.load) or not callable(self.state) or self.dispatch is not None and not callable(self.dispatch):
            raise ModelError('saved samples need pure load recipe/state callbacks and optional dispatch')
        object.__setattr__(self,'paths',paths)


def _digest(value):
    return hashlib.sha256(json.dumps(to_jsonable(value),sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def _discover(root,source,footprint):
    found=set()
    def failed(error):
        raise error
    for pattern in source.paths:
        path=Path(root)/pattern
        parts=path.parts
        magic=next((index for index,part in enumerate(parts) if any(c in part for c in '*?[')),None)
        if magic is None:
            footprint['directories'][str(path.parent)]=directory_stamp(path.parent)
            found.add(path)
            continue
        base=Path(*parts[:magic])
        footprint['files'][str(base)]=file_stamp(base)
        relative=Path(*parts[magic:]).as_posix()
        for directory,dirs,files in os.walk(base,onerror=failed):
            footprint['directories'][str(Path(directory))]=directory_stamp(directory)
            for name in (*dirs,*files):
                candidate=Path(directory)/name
                if matches_any(candidate.relative_to(base).as_posix(),[relative]):
                    found.add(candidate)
    return sorted(found,key=str)


def _width(model):
    """Only independently declared IDs/fields and source references choose pair scope.

    This is a bounded reference check, not an inference of business guards/effects.
    Opaque rule helpers keep an explicit relation limit rather than claiming unary.
    """
    if len(model.kinds)>1:
        return None,['saved samples currently need one declared object kind']
    if not model.kinds:
        return 1,[]
    ids=set(next(iter(model.kinds.values())))
    if len(ids)==1:
        return 1,[]
    limits=[]
    def held(value):
        found=set();active=set();done=set();frames=[(iter((value,)),None)]
        while frames:
            children,owner=frames[-1]
            try:
                item=next(children)
            except StopIteration:
                frames.pop()
                if owner is not None:
                    active.remove(owner);done.add(owner)
                continue
            kind=type(item)
            if kind is str:
                if item in ids:found.add(item)
                continue
            if kind is dict or kind is SettingValues:
                children=itertools.chain(dict.keys(item),dict.values(item))
            elif any(kind is selected for selected in (tuple,list,set,frozenset,Ids)):
                children=iter(item)
            else:
                if kind is not range and kind is not bytes and any(
                        name in type.__getattribute__(base,'__dict__')
                        for base in type.__getattribute__(kind,'__mro__')
                        for name in ('__iter__','__getitem__','keys','values','items')):
                    limits.append('saved object relation uses an opaque collection')
                continue
            token=id(item)
            if token in active:
                limits.append('saved object relation contains cyclic metadata')
                continue
            if token in done:continue
            active.add(token);frames.append((children,token))
        return found
    pair=any(isinstance(field.key,tuple) and len(held(field.key[1:]))>1 for field in model.fields)
    for rule in model.rules:
        if isinstance(rule.obj,tuple) and len(set(rule.obj)&ids)>1:
            pair=True
        related=[action for action in model.actions if rule.action in ('*',action.name)]
        if any(sum(any(_has_id(value,ids) for value in domain) for domain in action.domains)>1 for action in related):
            pair=True
        seen=set();pending=[fn for fn in (rule.pred,rule.when,rule.goal) if fn is not None]
        while pending:
            fn=pending.pop()
            if id(fn) in seen:
                continue
            seen.add(id(fn))
            if type(fn) is not types.FunctionType:
                limits.append('saved rule object relation is opaque: '+rule.name);pair=True
                continue
            for value in (*(fn.__defaults__ or ()),*(fn.__kwdefaults__ or {}).values()):
                if len(held(value))>1:pair=True
                if len(held(value))>2:
                    limits.append('saved relation exceeds the declared single/pair abstraction: '+rule.name)
            codes=[fn.__code__]
            while codes:
                code=codes.pop()
                literal_ids={value for value in code.co_consts if type(value) is str and value in ids}
                if len(literal_ids)>1 or rule.obj in ids and literal_ids-{rule.obj}:
                    pair=True
                if len(literal_ids)>2:
                    limits.append('saved relation exceeds the declared single/pair abstraction: '+rule.name)
                codes.extend(value for value in code.co_consts if type(value) is types.CodeType)
                for name in code.co_names:
                    value=fn.__globals__.get(name)
                    references=held(value)
                    if len(references)>1:
                        pair=True
                        if len(references)>2:
                            limits.append('saved relation exceeds the declared single/pair abstraction: '+rule.name)
                    elif type(value) is types.FunctionType and (value.__code__.co_filename==fn.__code__.co_filename or model.root and Path(value.__code__.co_filename).is_relative_to(model.root)):
                        pending.append(value)
            for cell in fn.__closure__ or ():
                try:
                    value=cell.cell_contents
                except ValueError:
                    continue
                if len(held(value))>1:
                    pair=True
                if len(held(value))>2:
                    limits.append('saved relation exceeds the declared single/pair abstraction: '+rule.name)
                if type(value) is types.FunctionType:
                    pending.append(value)
                elif type(value) is Rule:
                    pending.extend(item for item in (value.pred,value.when,value.goal) if item is not None)
    return (2 if pair else 1),sorted(set(limits))


def _prefix(source,file):
    recipes=tuple(source.load({'$file':file}))
    if not recipes or any(not isinstance(recipe,dict) for recipe in recipes):
        raise ModelError('saved sample load callback must return native prefix recipes ending with actual object IDs')
    json.dumps(recipes,allow_nan=False)
    return recipes


def _binding(model,source,raw,file,ids):
    original=model.adapter_binding
    start=copy.deepcopy(original.start)
    files=start.setdefault('files',{})
    if file in files:
        raise ModelError('saved sample arena filename overlaps an existing adapter input')
    files[file]=base64.b64encode(raw).decode()
    project=lambda snapshot:source.state(snapshot,ids)
    dispatch=(lambda value:source.dispatch(value,ids)) if source.dispatch else original.dispatch
    return replace(original,state=project,dispatch=dispatch,start=start,
                   prefix=(*original.prefix,*_prefix(source,file)))


def _project(model,source,snapshot,ids):
    try:
        projected=dict(source.state(snapshot,ids))
        fields={field.key:field for field in model.fields}
        if set(projected)!=set(fields):
            raise ModelError('saved sample projection must cover exactly the declared object slots/fields')
        if any(value not in fields[key].domain for key,value in projected.items()):
            raise session.UnsupportedWorld('actual saved state is outside the independently declared model domains')
        return tuple(projected[field.key] for field in model.fields)
    except (ModelError,session.UnsupportedWorld):
        raise
    except Exception as error:
        raise session.NativeEngineError(f'saved sample projection raised {type(error).__name__}: {error}',phase='judgment') from error


def analyze(root,loaded,bounds=Bounds(),*,full=False,previous=(),progress=None,observation=None):
    """Called only by the existing core part, never by Model.load or declarations."""
    from .native_evidence import evaluate_report
    root=Path(root).resolve();model=loaded.model
    sources=model.sample_sources
    coverage=dict(status='unchecked',reason='old saves not checked',files=[],starts=[],objects=0,
                  object_width=None,worker_pid=os.getpid(),limits=[],loads=[])
    result=dict(coverage=coverage,findings=[],native=[],reads=[],footprints=[],complete=True)
    if not sources:
        return result
    if model.adapter_binding is None:
        coverage.update(status='unknown',reason='saved samples need the actual native adapter')
        result['complete']=False
        return result
    width,limits=_width(model);coverage['object_width']=width;coverage['limits'].extend(limits)
    bounded=width is not None and not limits
    if not bounded:
        result['complete']=False
    counts={kind:width for kind in model.kinds} if bounded else {}
    narrowed=load_model(model.path,root,object_counts=counts)
    current=narrowed.model
    footprint=dict(files={},directories={},directory_uses={},environment={},reusable=True)
    result['footprints'].append(footprint)
    cases={};starts=set();reads=set()
    for index,declared in enumerate(sources):
        source=current.sample_sources[index]
        try:
            paths=_discover(root,source,footprint)
        except OSError as error:
            coverage['limits'].append(f'sample discovery unreadable: {error}');result['complete']=False
            continue
        for path in paths:
            relative=path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
            try:
                stamp=file_stamp(path)
                raw=path.read_bytes() if stamp.get('sha256') else None
            except OSError as error:
                footprint['files'][str(path)]={'unreadable':type(error).__name__}
                coverage['files'].append(dict(path=relative,version=source.version,status='unreadable'))
                coverage['limits'].append(f'{relative}: unreadable sample: {error}');result['complete']=False
                continue
            footprint['files'][str(path)]=stamp
            origin=dict(path=relative,version=source.version,sha256=stamp.get('sha256'),declaration=index,object_counts=counts)
            coverage['files'].append(origin)
            if not stamp.get('sha256'):
                coverage['limits'].append('sample unavailable or not a regular file: '+relative);result['complete']=False
                continue
            if hashlib.sha256(raw).hexdigest()!=stamp['sha256']:
                coverage['limits'].append('sample changed during capture: '+relative);result['complete']=False
                continue
            if path.is_relative_to(root):
                reads.add(relative)
            arena_file='saved-input/'+path.name
            probe=_binding(current,source,raw,arena_file,())
            try:
                actual=probe.execute(())
            except session.UnsupportedWorld as error:
                coverage['limits'].append(relative+': '+str(error));result['complete']=False
                continue
            coverage['loads'].append(actual)
            result['footprints'].append(actual['footprint'])
            starts.add('sample-file:'+source.version+':'+origin['sha256'])
            base_prefix=len(current.adapter_binding.prefix)
            if any(step['outcome']!='success' for step in actual['steps'][:base_prefix]):
                coverage['limits'].append(relative+': the original adapter setup did not complete');result['complete']=False
                continue
            failed=next((step for step in actual['steps'][base_prefix:] if step['outcome']=='crash'),None)
            if failed:
                result['findings'].append(make_finding('FILE CRASH',CONFLICT,model.id or model.name,
                    'saved input '+relative,'the actual saved-file loader raised '+failed['exception']['type'],sources=[source.source],
                    detail=dict(saved_sample=origin,exception=failed['exception'],native_load=len(coverage['loads'])-1),line=source.line))
                continue
            if any(step['outcome']!='success' for step in actual['steps']):
                coverage['limits'].append(relative+': saved-file loading was refused');result['complete']=False
                continue
            if not any(row['path']==arena_file for row in actual['footprint'].get('world_reads',())):
                coverage['limits'].append(relative+': the actual loader did not read the supplied file');result['complete']=False
                continue
            ids=plain(actual['steps'][-1]['value'])
            if not isinstance(ids,(list,tuple)) or any(type(value) not in (str,int) for value in ids) or len(set(ids))!=len(ids):
                raise ModelError('saved load prefix must end with the actual distinct object-ID list')
            coverage['objects']+=len(ids)
            if not bounded:
                continue
            if len(ids)<width:
                # No invented partner: a genuinely unary file cannot witness a pair.
                coverage['limits'].append(relative+': not enough actual objects for the declared relational rule')
                result['complete']=False
                continue
            for selected in itertools.permutations(ids,width):
                try:
                    state=_project(current,source,actual['final'],selected)
                except session.UnsupportedWorld as error:
                    coverage['limits'].append(relative+': '+str(error));result['complete']=False
                    continue
                signature=_digest(state)
                token='sample:'+source.version+':'+origin['sha256']+':'+signature
                starts.add(token)
                context={**origin,'ids':list(selected),'signature':signature}
                if signature in cases:
                    cases[signature]['origins'].append(context)
                else:
                    cases[signature]=dict(state=state,binding=_binding(current,source,raw,arena_file,selected),
                        context=context,origins=[context])
    model.__dict__['_saved_sample_starts']=sorted(starts)
    current_observation = observation() if observation is not None else None
    for signature,case in sorted(cases.items()):
        context=case['context'];current.adapter_binding=case['binding']
        current.__dict__['_saved_sample_context']=context
        report=check_model(narrowed,bounds,reduce=False,start=case['state'],progress=progress)
        selected_previous=[]
        native=evaluate_report(root,report,selected_previous,full=full,observation=current_observation)
        for check in native['checks'].values():
            check['saved_sample']=context
        if native.get('walk'):
            native['walk']['saved_sample']=context
        for finding in report.findings:
            finding.detail['saved_sample']=context
        result['findings'].extend(report.findings)
        result['native'].append(native)
        result['complete']&=report.graph.complete
        coverage['starts'].append(dict(signature=signature,origins=case['origins'],states=len(report.graph.states),complete=report.graph.complete))
    present={finding.id for finding in result['findings']}
    for entry in previous:
        context=saved_origin(entry)
        if not context or entry['id'] in present or entry['kind']=='MODEL DRIFT' and any(item['status']=='drift' for item in result['native']):
            continue
        try:
            restored=restore_start(root,model.path,context,bounds)
        except (ModelError,OSError,session.UnsupportedWorld) as error:
            coverage.setdefault('retained_limits',[]).append(entry['id']+': '+str(error))
            continue
        native=evaluate_report(root,restored,[entry],full=full,observation=current_observation)
        for check in native['checks'].values():
            check['saved_sample']=restored.graph.model.__dict__['_saved_sample_context']
        if native.get('walk'):
            native['walk']['saved_sample']=restored.graph.model.__dict__['_saved_sample_context']
        result['native'].append(native)
    model.__dict__['_saved_sample_starts']=sorted(starts)
    result['reads']=sorted(reads)
    if coverage['files'] or coverage['limits']:
        coverage.update(status='checked' if result['complete'] and not coverage['limits'] else 'unknown',reason='finite actual saved-file/object starts')
    if coverage['limits']:
        result['complete']=False
    return result


def saved_origin(entry):
    detail=entry.get('detail',{})
    return detail.get('saved_sample') or detail.get('native_origin',{}).get('saved_sample')


def merge_native(native,sampled):
    """Attach archived starts to the existing core receipt, with one comparison owner."""
    statuses=[native['status']]
    for number,item in enumerate(sampled['native']):
        statuses.append(item['status'])
        rename={key:'saved:'+str(number)+':'+key for key in item['checks']}
        native['checks'].update({rename[key]:value for key,value in item['checks'].items()})
        if item.get('walk'):
            native['checks']['saved:'+str(number)+':walk']=item['walk']
        for group in ('confirmed','closures'):
            for identifier,proof in item[group].items():
                proof=copy.deepcopy(proof)
                if 'checks' in proof:
                    proof['checks']=[rename.get(key,key) for key in proof['checks']]
                native[group][identifier]=proof
        for group in ('footprints','writes','limits'):
            native[group].extend(item[group])
        native['reads']=sorted(set(native['reads'])|set(item['reads']))
        native.setdefault('code_inputs',{}).update(item.get('code_inputs',{}))
    native['footprints'].extend(sampled['footprints'])
    native['reads']=sorted(set(native['reads'])|set(sampled['reads']))
    if sampled['coverage']['status']=='unknown':
        statuses.append('unknown')
        native['limits'].extend(sampled['coverage']['limits'])
    native['status']='drift' if 'drift' in statuses else 'unknown' if 'unknown' in statuses else native['status']
    if native['status'] in ('drift','unknown'):
        native['closures'].clear()
        native['confirmed'].clear()
    return native


def coverage_summary(coverage):
    """Compact public boundary; raw native loads remain in the private core part."""
    return dict(status=coverage['status'],reason=coverage['reason'],files=len(coverage['files']),
                objects=coverage['objects'],starts=len(coverage['starts']),object_width=coverage['object_width'],
                versions=sorted({row['version'] for row in coverage['files']}),limits=coverage['limits'])


def restore_start(root,path,context,bounds=Bounds()):
    """Re-observe the actual original file; expected state is never a native input."""
    root=Path(root).resolve()
    loaded=load_model(path,root,object_counts=context['object_counts'])
    model=loaded.model
    try:
        source=model.sample_sources[context['declaration']]
    except (KeyError,IndexError,TypeError) as error:
        raise ModelError('the original saved-file declaration is unavailable') from error
    if source.version!=context['version']:
        raise ModelError('the original saved-file source version changed')
    file=root/context['path']
    if file_stamp(file).get('sha256')!=context['sha256']:
        raise ModelError('the original saved-file bytes are missing or changed')
    binding=_binding(model,source,file.read_bytes(),'saved-input/'+file.name,tuple(context.get('ids',())))
    actual=binding.execute(())
    if any(step['outcome']!='success' for step in actual['steps']):
        raise ModelError('the original saved file no longer loads normally')
    if not any(row['path']=='saved-input/'+file.name for row in actual['footprint'].get('world_reads',())):
        raise ModelError('the original saved file was not actually read')
    actual_ids=plain(actual['steps'][-1]['value'])
    if not isinstance(actual_ids,(list,tuple)) or any(type(value) not in (str,int) for value in actual_ids) or len(set(actual_ids))!=len(actual_ids):
        raise ModelError('the original saved object-ID list is unavailable')
    ids=tuple(context.get('ids',actual_ids[:max(context['object_counts'].values(),default=1)]))
    if not set(ids)<=set(actual_ids):
        raise ModelError('the original saved object IDs are no longer available from the actual loader')
    state=_project(model,source,actual['final'],ids)
    context={**context,'ids':list(ids),'signature':_digest(state)}
    binding=_binding(model,source,file.read_bytes(),'saved-input/'+file.name,ids)
    model.adapter_binding=binding
    model.__dict__['_saved_sample_context']=context
    return check_model(loaded,bounds,reduce=False,start=state)
