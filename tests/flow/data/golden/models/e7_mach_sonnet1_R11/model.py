from machine import Machine, need
T=["T1","T2"]; M=["M1","M2"]; B=["A","B"]
m = Machine("bring", settings=dict(hold_days=2))
S = m.settings
# where: shop (on shelf/held/available), transit, loan
m.field("where", ["shop","transit","loan"], "shop", over=T)
m.field("branch", B, "A", over=T)
m.field("holder", [None]+M, None, over=T)       # held for
m.field("queue", [(),("M1",),("M2",),("M1","M2"),("M2","M1")], (), over=T)
m.field("renter", [None]+M, None, over=T)
m.field("age", range(0,S["hold_days"]), 0, over=T)
m.field("sentvia", ["none","staff","bring"], "none", over=T)   # why in transit

def back_in_shop(s,t):
    s["where",t]="shop"; s["sentvia",t]="none"
    q=s["queue",t]
    if q: s["holder",t]=q[0]; s["queue",t]=q[1:]; s["age",t]=0

@m.action(t=T,mem=M)
def rent(s,t,mem):
    need(s["where",t]=="shop","not in shop")   # DESIGN: transit refused
    need(s["holder",t] in (None,mem),"held for other")
    s["where",t]="loan"; s["renter",t]=mem; s["holder",t]=None; s["age",t]=0
@m.action(t=T)
def give_back(s,t):
    need(s["where",t]=="loan","")
    s["renter",t]=None; back_in_shop(s,t)
@m.action(t=T,mem=M)
def reserve(s,t,mem):
    need(s["where",t]=="loan" or (s["where",t]=="shop" and s["holder",t] not in (None,mem)),"")
    need(s["renter",t]!=mem and mem not in s["queue",t],"")
    need(len(s["queue",t])<2,"full")
    s["queue",t]=s["queue",t]+(mem,)
@m.action(t=T,mem=M)
def cancel(s,t,mem):
    if mem in s["queue",t]:
        s["queue",t]=tuple(x for x in s["queue",t] if x!=mem)
    else:
        need(s["holder",t]==mem,"none")
        s["holder",t]=None
        if s["where",t]=="shop": back_in_shop(s,t)     # DESIGN: in transit stays in transit
@m.action(t=T,to=B)
def transfer(s,t,to):
    need(s["where",t]=="shop" and s["holder",t] is None,"only available")
    need(s["branch",t]!=to,"same")
    s["branch",t]=to; s["where",t]="transit"; s["sentvia",t]="staff"
@m.action(t=T,mem=M,to=B)
def bring(s,t,mem,to):
    need(s["holder",t]==mem and s["where",t]=="shop","not held for you / not on shelf")
    need(s["branch",t]!=to,"same branch")
    s["branch",t]=to; s["where",t]="transit"; s["sentvia",t]="bring"
@m.action(t=T)
def receive(s,t):
    need(s["where",t]=="transit","")
    if s["sentvia",t]=="bring":
        s["where",t]="shop"; s["sentvia",t]="none"; s["age",t]=0   # hold kept, clock restarts
    else: back_in_shop(s,t)
@m.action()
def advance(s):
    for t in T:
        if s["holder",t] is not None:
            if s["where",t]=="transit": continue          # DESIGN: clock waits in transit
            s["age",t]+=1
            if s["age",t]>=S["hold_days"]:
                s["holder",t]=None; s["age",t]=0; back_in_shop(s,t)

m.option("bring", lambda s,mem,t,to: s["holder",t]==mem and s["where",t]=="shop" and s["branch",t]!=to,
         action="bring", mem=M, t=T, to=B)
m.after("bring keeps holder","bring",lambda b,a,t,mem,to: a["holder",t]==mem and a["queue",t]==b["queue",t])
m.after("receive of brought keeps holder","receive",lambda b,a,t: b["sentvia",t]!="bring" or a["holder",t]==b["holder",t])
m.only_when("no rent in transit","rent",lambda s,t,mem: s["where",t]!="transit")
m.progress("brought tool arrives", over=T, when=lambda s,t: s["sentvia",t]=="bring", goal=lambda s,t: s["where",t]!="transit")
m.progress("held tool gets collected or freed", over=T, when=lambda s,t: s["holder",t] is not None, goal=lambda s,t: s["holder",t] is None)
MACHINE=m
