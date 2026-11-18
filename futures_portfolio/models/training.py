"""Chronological Extra Trees fitting with training-only imputation."""
import pandas as pd
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from futures_portfolio.factors.selection import panel

def fit_model(r,classes,cutoff,features):
    x,target,return_date=panel(r,classes)
    label=target.gt(0).astype(float).where(target.notna()&target.ne(0))
    known=return_date.lt(pd.Timestamp(cutoff))&label.notna()
    model=make_pipeline(SimpleImputer(strategy='median',keep_empty_features=True),
        ExtraTreesClassifier(n_estimators=200,max_depth=6,min_samples_leaf=30,max_features=.7,random_state=5260,n_jobs=2))
    model.fit(x.loc[known,features],label.loc[known].astype(int))
    audit=dict(last_training_label=str(return_date.loc[known].max().date()),training_rows=int(known.sum()),
               training_label_start=str(return_date.loc[known].min().date()),feature_count=len(features))
    return model,audit,(x,target,return_date)

