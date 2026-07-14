#!/usr/bin/env python3
"""adv_figures.py -- required figures for the adversarial-training experiment."""
import os, json
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG=os.path.join(ROOT,"figures"); REP=os.path.join(ROOT,"reports")
agg=json.load(open(os.path.join(ROOT,"advtrain_results.json")))["aggregate"]
P=pd.read_csv(os.path.join(ROOT,"paired_results.csv"))
def g(m,c,k): return agg[m][c]["mean"][k]
def gs(m,c,k): return agg[m][c]["std"][k]
C_M0="#e34948"; C_AUG="#2a78d6"; C_XGB="#eda100"; C_XGBA="#1baf7a"
plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,
                     "axes.grid":True,"grid.alpha":0.25,"figure.dpi":140})

# 1. clean-performance comparison
def fig_clean():
    models=["opcode-histogram RF","opcode-histogram XGBoost","opcode-histogram XGBoost-aug","AuthGuard-M0","AuthGuard-aug"]
    mets=["AUPRC","AUROC","recall","FPR"]
    x=np.arange(len(mets)); w=0.16
    fig,ax=plt.subplots(figsize=(8,4.3))
    colors=["#999999","#eda100","#1baf7a","#e34948","#2a78d6"]
    for i,m in enumerate(models):
        vals=[g(m,"M0",k) for k in mets]
        ax.bar(x+(i-2)*w, vals, w, label=m, color=colors[i])
    ax.set_xticks(x); ax.set_xticklabels(["AUPRC","AUROC","recall","FPR(benign)"])
    ax.set_title("Clean M0 held-out performance (family-grouped, 5 folds)")
    ax.legend(fontsize=7.5,frameon=False,ncol=2); ax.set_ylim(0,1)
    fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig_advtrain_clean.png")); plt.close(fig)

# 2. seen augmentation conditions
def fig_seen():
    conds=["M1","M2","F25","F50","F100"]; x=np.arange(len(conds))
    fig,(a1,a2)=plt.subplots(1,2,figsize=(9.5,4))
    for m,c,l in [("AuthGuard-M0",C_M0,"AuthGuard-M0"),("AuthGuard-aug",C_AUG,"AuthGuard-aug")]:
        a1.plot(x,[g(m,cc,"recall") for cc in conds],marker="o",color=c,label=l)
        a2.plot(x,[g(m,cc,"benign_flag_rate") for cc in conds],marker="s",color=c,label=l)
    for a,t in [(a1,"malicious recall"),(a2,"benign flag rate (FPR)")]:
        a.set_xticks(x); a.set_xticklabels(conds); a.set_title(t); a.legend(frameon=False,fontsize=8); a.set_ylim(0,1)
    fig.suptitle("Seen augmentation conditions",fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig_advtrain_seen.png")); plt.close(fig)

# 3. held-out conditions
def fig_held():
    conds=["M3","F200"]; x=np.arange(len(conds)); w=0.19
    models=[("AuthGuard-M0",C_M0),("AuthGuard-aug",C_AUG),("opcode-histogram XGBoost",C_XGB),("opcode-histogram XGBoost-aug",C_XGBA)]
    fig,(a1,a2)=plt.subplots(1,2,figsize=(9.5,4.2))
    for i,(m,c) in enumerate(models):
        a1.bar(x+(i-1.5)*w,[g(m,cc,"recall") for cc in conds],w,color=c,label=m,
               yerr=[gs(m,cc,"recall") for cc in conds],capsize=3)
        a2.bar(x+(i-1.5)*w,[g(m,cc,"benign_flag_rate") for cc in conds],w,color=c,label=m)
    for a,t in [(a1,"malicious recall"),(a2,"benign flag rate (FPR)")]:
        a.set_xticks(x); a.set_xticklabels(["M3\n(held-out condition)","+200%\n(held-out severity)"]); a.set_title(t); a.set_ylim(0,1)
    a1.legend(fontsize=7,frameon=False,ncol=1,loc="lower left")
    fig.suptitle("Held-out mutation conditions and severities",fontweight="bold")
    fig.tight_layout(); fig.savefig(os.path.join(FIG,"fig_advtrain_heldout.png")); plt.close(fig)

# 4. malicious vs benign score distributions under M0, +100%, +200%
def fig_scoredist():
    conds=["M0","F100","F200"]
    fig,axes=plt.subplots(2,3,figsize=(11,5.6),sharex=True,sharey=True)
    for col,cond in enumerate(conds):
        for row,model in enumerate(["AuthGuard-M0","AuthGuard-aug"]):
            ax=axes[row][col]
            d=P[(P.model==model)&(P.condition==cond)]
            thr=d["threshold"].iloc[0]
            ax.hist(d[d.true_label==1]["raw_score"],bins=30,alpha=0.6,color=C_M0,label="malicious",density=True)
            ax.hist(d[d.true_label==0]["raw_score"],bins=30,alpha=0.6,color=C_AUG,label="benign",density=True)
            ax.axvline(thr,color="k",ls="--",lw=1)
            if row==0: ax.set_title(cond)
            if col==0: ax.set_ylabel(f"{model}\ndensity",fontsize=8)
            if row==0 and col==0: ax.legend(fontsize=7,frameon=False)
    fig.suptitle("Score distributions (malicious vs benign); dashed = frozen threshold",fontweight="bold")
    fig.supxlabel("model score"); fig.tight_layout()
    fig.savefig(os.path.join(FIG,"fig_advtrain_scoredist.png")); plt.close(fig)

for fn in [fig_clean,fig_seen,fig_held,fig_scoredist]:
    fn(); print("wrote",fn.__name__)
