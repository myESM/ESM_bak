#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging, json, requests, os
from cryptography.fernet import Fernet
from flask import Flask, jsonify, make_response, request
import predicting, training

app = Flask(__name__)

# 404 message for bad requests
@app.errorhandler(404)
def not_found(error):
  return make_response(jsonify({"error": "404 NOT FOUND"}), 404)

# 500 message for bad requests
@app.errorhandler(500)
def not_found(error):
  return make_response(jsonify({"error": "500 INTERNAL SERVER ERROR"}), 500)

# run eta_malware api
@app.route("/eta_fl/api/pred", methods=["GET"])
def eta_fl_predict():
  #check the parameters
  es_index = request.args.get("index", None)
  es_start_time = request.args.get("start_time", None)
  es_end_time = request.args.get("end_time", None)
  if es_index == None or es_start_time == None or es_end_time == None:
    missing_parameter = ""
    if es_index == None:
      missing_parameter += " {es_index} "
    if es_start_time == None:
      missing_parameter += " {es_start_time} "
    if es_end_time == None:
      missing_parameter += " {es_end_time} "
    return jsonify({"error": "Missing parameter" + missing_parameter})
  else:
    load_main = predicting.Main()
    res = load_main.queryES(es_index, es_start_time, es_end_time)
    df = load_main.toDf(res)
    if df.shape[0] != 0:
      df_fin, df_id = load_main.processData(df)
      pred = load_main.predict(df_fin)
      output = load_main.toJSON(pred, df_fin, df_id)
      load_main.toES(output)
    return jsonify({"result": "Done"})

@app.route("/eta_fl/api/train", methods=["GET"])
def eta_fl_train():
  #check the parameters
  es_edge_index = request.args.get("edge_index", None)
  es_alert_index = request.args.get("alert_index", None)
  es_malware_index = request.args.get("malware_index", None)
  if es_edge_index == None or es_alert_index == None or es_malware_index == None:
    missing_parameter = ""
    if es_edge_index == None:
      missing_parameter += " {es_edge_index} "
    if es_alert_index == None:
      missing_parameter += " {es_alert_index} "
    if es_malware_index == None:
      missing_parameter += " {es_malware_index} "
    return jsonify({"error": "Missing parameter" + missing_parameter})
  else:
    load_main = training.Main()
    best_params = None
    preds_sel = None
    load_main.initialEnv()
    res2 = load_main.queryES2(es_alert_index)
    label = load_main.toAlertDf(res2)
    res3 = load_main.queryES3(es_malware_index)
    malware = load_main.toMalDf(res3)
    for idx1 in load_main.esIdxList(es_edge_index):
      res1 = load_main.queryES1(idx1)
      edge = load_main.toEdgeDf(res1)
      if len(label) != 0:
        benign = load_main.filterBenign(edge, label)
      else:
        benign = edge.copy()
      del edge
      X, y = load_main.processData(benign, malware)
      del benign
      if best_params == None:
        best_params = load_main.paraGridSearch(X, y)
      if preds_sel == None:
        fmp = load_main.model(best_params, X, y, fmp=True)
        preds_sel = load_main.featureSelect(fmp)
      X = X[preds_sel]
      load_main.model(best_params, X, y, save=True)
      del X, y
    return jsonify({"result": "Done"})

@app.route("/eta_fl/api/upload", methods=["GET"])
def eta_fl_upload():
  best_params = json.load(open(os.path.dirname(os.path.abspath(__file__))+"/model/bast_params.json", "r"))
  data_byte = json.dumps(best_params).encode("utf-8")
  CRYPT_KEY = 'qfLSIQpQ4ctzZAJWdOa_p2A2VbDjVJ_Oy5NAa-7vueI='
  cipher = Fernet(CRYPT_KEY)
  encrypted_message = cipher.encrypt(data_byte)
  my_p = {'model_parameter':encrypted_message}
  # response = requests.get('http://192.168.70.120:8080/eta_fl/upload', params=my_p)
  response = requests.get('https://test.esm.secbuzzer.co/eta_fl/upload', params=my_p)
  return jsonify({"result": "Done"})

@app.route("/eta_fl/api/get_params", methods=["GET"])
def eta_fl_get_params():
  # decrypted_params = requests.get("http://192.168.70.120:8080/eta_fl/download")
  decrypted_params = requests.get("https://test.esm.secbuzzer.co/eta_fl/download")
  decrypted_message = decrypted_params.text.encode("utf-8")
  CRYPT_KEY = 'qfLSIQpQ4ctzZAJWdOa_p2A2VbDjVJ_Oy5NAa-7vueI='
  cipher = Fernet(CRYPT_KEY)
  new_params_byte = cipher.decrypt(decrypted_message)
  new_params = json.loads(new_params_byte)
  if len(new_params) > 0:
    with open(os.path.dirname(os.path.abspath(__file__))+"/model/bast_params.json", "wb") as f:
      f.write(json.dumps(new_params).encode("utf-8"))
      f.close()
  else:
    pass
  return jsonify({"result": "Done"})

app.run(host="0.0.0.0", port=5000, debug=False)
