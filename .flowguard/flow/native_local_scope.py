"""Live locals and explicit pure parsing do not become ambient resource reads."""
from flowguard.flow import Model, need
m=Model('native local closure scope')
m.field('phase', ('new','known','unknown'), 'new', source='R15')
m.field('scope', ('pending','local','persistent','global-alias','pure-parse','clock','builtin-truth','custom-truth',
                 'attribute-only','opaque-global','written-global','local-import','module-mutation','unselected-import'), 'pending', source='R15')
@m.action(scope=('local','persistent','global-alias','pure-parse','clock','builtin-truth','custom-truth',
                 'attribute-only','opaque-global','written-global','local-import','module-mutation','unselected-import'), source='R15')
def observe(s,scope):
    need(s['phase']=='new')
    s['scope']=scope
    s['phase']='known' if scope in ('local','pure-parse','builtin-truth','attribute-only','local-import','unselected-import') else 'unknown'
m.terminal('phase', ('known','unknown'), source='R15')
m.always('attribute names alone do not read a same-named ambient global',lambda s:
         (s['phase']=='known') == (s['scope'] in ('local','pure-parse','builtin-truth','attribute-only','local-import','unselected-import')),source='R15')
m.always('persistent closure and package aliases remain guarded',lambda s:
         s['scope'] not in ('persistent','global-alias','clock','custom-truth','opaque-global','written-global','module-mutation') or s['phase']=='unknown',source='R15')
m.reach('attribute-only access survives an unrelated opaque global',lambda s:
        s['scope']=='attribute-only' and s['phase']=='known',source='R15')
m.reach('an actually consumed opaque global remains unknown',lambda s:
        s['scope']=='opaque-global' and s['phase']=='unknown',source='R15')
m.reach('a write to ambient business state remains unknown',lambda s:
        s['scope']=='written-global' and s['phase']=='unknown',source='R15')
m.reach('binding a known imported module is local bookkeeping',lambda s:
        s['scope']=='local-import' and s['phase']=='known',source='R15')
m.reach('mutating a consumed imported module remains unknown',lambda s:
        s['scope']=='module-mutation' and s['phase']=='unknown',source='R15')
m.reach('an unselected import never executes opaque metadata',lambda s:
        s['scope']=='unselected-import' and s['phase']=='known',source='R15')
MODEL=m
