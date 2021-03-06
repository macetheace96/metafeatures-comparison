from pathlib import Path 
import numpy as np 
import os
from arff2pandas import a2p
import pandas as pd
from io import StringIO
import time
import csv

from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import cohen_kappa_score, precision_score, recall_score, roc_auc_score, f1_score
from sklearn.model_selection import cross_val_predict

import weka.core.jvm as jvm
import weka.core.converters as converters
from weka.core.converters import Loader
from weka.classifiers import Classifier, Evaluation, PredictionOutput
from weka.core.classes import Random
from weka.filters import Filter

jvm.start(max_heap_size="8192m")
loader = Loader(classname="weka.core.converters.ArffLoader")

def file_find(base_dir, file_ext="arff"):
    paths = []
    for base, directories, files in os.walk(base_dir):
        for file_name in files:
            if("."+file_ext in file_name):
                paths.append(base+"/"+file_name)
    return paths

def load_arff(infile_path):
    f = open(infile_path)
    print(infile_path)
    dataframe = a2p.load(f)
    dataframe = dataframe.rename(index=str, columns={dataframe.columns[-1]: 'target'})
    return dataframe

def _dtype_is_numeric(dtype):
        return "int" in str(dtype) or "float" in str(dtype)

def _preprocess_data(dataframe):
        series_array = []
        for feature in dataframe.columns:
            feature_series = dataframe[feature]
            col = feature_series.as_matrix()
            dropped_nan_series = feature_series.dropna(axis=0,how='any')
            num_nan = col.shape[0] - dropped_nan_series.shape[0]
            if num_nan != col.shape[0]:
	            col[feature_series.isnull()] = np.random.choice(dropped_nan_series, num_nan)
	            if not _dtype_is_numeric(feature_series.dtype):
	                feature_series = pd.get_dummies(feature_series)
	            series_array.append(feature_series)
        preprocessed_dataframe = pd.concat(series_array, axis=1, copy=False)
        return preprocessed_dataframe

def compute_sklearn(model,X,y_true):
	return cross_val_predict(model,X,y_true,cv=10)

def compute_weka(model,data,pout):
	return evl.crossvalidate_model(model, data, 10, Random(1), pout)

def make_csv(file, data, head):
	with open(file, 'w', newline='') as csvfile:
		writer = csv.writer(csvfile, delimiter=',', quoting=csv.QUOTE_NONE)
		writer.writerow(head)
		for x in data:
			writer.writerow(list(x))

def print_as_csv(data):
	for x in data:
		print(x)
	
files = file_find("./datasets")
files.sort()

weka_f = []
weka_speed = []
sklearn_f = []
sklearn_speed = []
cod_scores = []

weka_tree = Classifier(classname="weka.classifiers.trees.RandomTree", options=["-depth", "3"])
sklearn_tree = DecisionTreeClassifier(splitter='random',max_depth=3)

for file in files:

	#sklearn values
	dataset = load_arff(file)
	y_true = list(dataset["target"])
	X = dataset.drop("target", axis=1)
	X = _preprocess_data(X)
	sklearn_tree.fit(X,y_true)

	start = time.time()
	results = compute_sklearn(sklearn_tree,X,y_true)
	end = time.time()

	sklearn_speed.append(end-start)
	s_pred = results
	sklearn_f.append(f1_score(y_true,s_pred,average='weighted'))

	#weka values
	data = loader.load_file(file)
	data.class_is_last()
	weka_tree.build_classifier(data)
	w_pred = []
	pout = PredictionOutput(classname="weka.classifiers.evaluation.output.prediction.CSV")
	evl = Evaluation(data)
	start = time.time()
	compute_weka(weka_tree,data,pout)
	end = time.time()
	results = pd.read_csv((StringIO(str(pout))),sep=',')
	results = list(results["predicted"])
	w_pred = []
	for x in results:
		w_pred.append(str(x)[2:])
	weka_f.append(evl.weighted_f_measure)
	weka_speed.append(end-start)

	#print predictions

	#cod values
	total_matches = 0
	for i in range(len(s_pred)):
		if s_pred[i] != w_pred[i]:
			total_matches = total_matches+1
	cod = total_matches/len(s_pred)
	cod_scores.append(cod)

f_differences = []
for x,y in zip(weka_f,sklearn_f):
	temp = x - y
	if not np.isnan(temp):
		f_differences.append(x-y)

speed_differences = []
for x,y in zip(weka_speed,sklearn_speed):
	temp = x - y
	if not np.isnan(temp):
		speed_differences.append(x-y)

# make_csv('f_scores.csv',f_differences,'f scores')
# make_csv('speed_scores.csv',speed_differences, 'speed scores')
# make_csv('cod_scores.csv',cod_scores, 'cod scores')

print_as_csv(f_differences)
print()
print_as_csv(speed_differences)
print()
print_as_csv(cod_scores)
#print(speed_differences)
#print(f_differences)
#print(cod_scores)
jvm.stop()
