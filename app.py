#!/usr/bin/env python
# coding: utf-8
# Author : *ASWIN PRABHAKARAN*
# Version : 0.1
# Dated : 02-Aug-2022
# Execution Command: Python backend.py -model_path <local_file_path> -ICD_credentials_path <local_file_path> -output <local_file_path>

import requests
import json
import os
import argparse

from flask_cors import CORS, cross_origin
from flask import Flask, request, flash, jsonify, render_template
import sys
import pickle
import time
import spacy

from nltk.corpus import stopwords

# Default Installations
app = Flask(__name__)
cors = CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

#################################################################################################################
############################################# STATIC Functions ##################################################


def load_SPACY_NER_model(model_path):
        
    """
    StandAlone function written to load the SPACY model from the given path

    :param model_path - file system path wher model is present in string format  
    :return - The SPACY model object 
    
    """
    
    if not os.path.exists(model_path):
        raise ValueError("The given path - {} doesnt exists".format(model_path))
        
    try:
        ner_model = spacy.load(model_path)
    except: 
        raise ValueError("Unable to Load the model from the path - {}".format(model_path))
        
        
    return ner_model


def spacy_NER_inference(ner_model, input_sentence):
    
    """
    Function to run the NER model for extracting the entities on the given input sentence
    
    :param input_sentence - Input sentence for which entities has to be extracted using SPACY NER MODEL
    :return - List of entities and its label as predicted by the model. Example [(Entitiy, label),....(Entitiy, label)]
    
    """
    
    predictions = ner_model(input_sentence)
    
    pred_entity_and_label = [(ent.text, ent.label_) for ent in predictions.ents]
    
    return pred_entity_and_label


def get_bearer_token():
    
    """
    The bearer token has to be generated every few minutes. 
    If we use the same bearer token , the authentication will fail.
    Hence the request must include a valid and non-expired bearer token in the Authorization header.
    
    :return - regenerated bearer token in string format
    
    """
    
    # get the OAUTH2 token

    # set data to post
    payload = {'client_id': WHO_ICD_logiin_credentials["client_id"], 
               'client_secret': WHO_ICD_logiin_credentials['client_secret'], 
               'scope': WHO_ICD_logiin_credentials['scope'], 
               'grant_type': WHO_ICD_logiin_credentials['grant_type']}
    
    
    try:
        # make request
        r = requests.post(WHO_ICD_logiin_credentials["token_endpoint"], data=payload, verify=False).json()
        token = r['access_token']
    except:
        raise ValueError("Unable to generate Bearer Token")
        
    
    return token


def clean_entity_token(entity_text):
    
    # Removing any starting/tailing spaces and converting the token to lowercase
    entity_text = entity_text.strip().lower()
    
#     # If the token contains any char which is non-alphbetical, removing it
#     token = [x for x in token if x.isalpha()]
#     token = "".join(token)
    
#     # Stopwords removal
#     if token in stopwords.words("english"):
#         token = None
    
    return entity_text


def get_WHO_codes(entities):
    
    """
    The purpose of this function is to call the API of WHO-ICD site and get the respose and validate it.
    Once the response is validated, then convert the response to JSON and grab the desired fields.
    Based on some post-processing logic, for every entity that is recognise by the NER model, we display the following: 
    
    1) Top 3 Code and its score for each entity recognized by model
    
    :param entities: List of entities predicted by the model 
    :return - dict with entity  as keys and codes, score as values. 
    Example {
            entity_text: [(code, score),...,(code, score)],
            entity_text: [(code, score),...,(code, score)],
            }  
    
    """
    
    res_dict = {}
    
    new_url = "https://id.who.int/icd/release/11/2022-02/mms/search"
    
    if len(entities) == 0:
        return res_dict
    
    # calling the function to regenerate the token which grants access to API for a shirt time
    token = get_bearer_token()
    
    for ent_text, _ in entities:
        ent_text = clean_entity_token(entity_text=ent_text)
        
        # HTTP header fields to set
        headers = {'Authorization':  'Bearer '+token, 'Accept': 'application/json',  
                   'Accept-Language': 'en', 'API-Version': 'v2'}
        
        input_dict = {"linearizationname": "mms", "releaseId": "2022-02", "q": ent_text, 
                       "API-Version": "v2", "Accept-Language": "en"}
        
        try:
            response = requests.get(new_url, input_dict, headers=headers)
            if response.status_code == 200:
                response_json = response.json()

                if len(response_json['destinationEntities']) != 0:
                    score_and_icd11_code = [(item['score'], item['theCode']) for item in response_json['destinationEntities']]
                else:
                    score_and_icd11_code = []
                    
                score_and_icd11_code = sorted(score_and_icd11_code, key=lambda item:item[0], reverse=True)
                res_dict[ent_text] = score_and_icd11_code[:3]
            else:
                print("Received Status code of {}".format(response.status_code))
        except Exception as inst:
            print(type(inst), inst)    # the exception instance and the exception
            print("Some other exception happened. Need to figure out what...?")
            
            
    return res_dict


#################################################################################################################
################################ FUNCTIONS FOR ROUTE(FLASK API's) ###############################################

@app.route("/")
def hello():
    # return "Welcome to the ICD-11 Code Mapper for Medical Records Using Named Entity Recognition"
    return render_template('index.html')

@app.route("/get_icd11_codes_for_sentence", methods=['POST'])
def NER_analysis():
    
    input_data_dict = request.get_json()
    print("\nInput received : ", input_data_dict)

    # Create the standard return dict with values
    output_data_dict = dict()

    mandatory_inputs = ['sentence']
    missing_mandatory_inputs = [field for field in mandatory_inputs if field not in input_data_dict]
    
    if len(missing_mandatory_inputs) != 0:
        output_data_dict['status'] = "Bad Request - Found Misising Values"
        output_data_dict['Missing Fields'] = missing_mandatory_inputs
    else:
        input_sentence = input_data_dict['sentence']
        ent_and_label_list = spacy_NER_inference(ner_model=SPACY_NER_MODEL, input_sentence=input_sentence)
        ent_icdcode_dict = get_WHO_codes(entities=ent_and_label_list)
        output_data_dict['predictions'] = ent_icdcode_dict
        
    
    return jsonify(output_data_dict)


if __name__ == "__main__":

    ap = argparse.ArgumentParser()
    ap.add_argument("-model_path", "--model_path", required = False, default = "./spacy_model/model-best/", type = str, help = "path to trained SPACY model")
    ap.add_argument("-ICD_credentials_path", "--ICD_credentials_path", required = False, default = "./WHO_ICD_logiin_credentials.json", type = str, help = "path to ICD Credentials JSON")
    ap.add_argument("-output", "--output", required = False, type = str, help = "path to output everything this script produces")
    ap.add_argument("-enable_failure_log", "--enable_failure_log", action = "store_true")
    args = vars(ap.parse_args())
    print(args)
    
    basedir = os.path.abspath(os.path.dirname(__file__))
    print("Base Dir : {}".format(basedir)) 
    
    # Loading the credentials for accessing the API from WHO-ICD-11
    with open(args['ICD_credentials_path'], 'r') as fin:
        WHO_ICD_logiin_credentials = json.load(fin)
      
    # Loading the model from the supplied path
    SPACY_NER_MODEL = load_SPACY_NER_model(model_path= args['model_path'])
        
    # Dump the processing logs if logging is enabled
    if args['enable_failure_log']:

        #Path for storing the processing outputs
        output = args['output']
        if not os.path.exists(output):
            print("creating : {}".format(output))
            os.makedirs(output)

        log_file_path = os.path.join(output, 'Processing.log')
        if os.path.exists(log_file_path):
            os.remove(log_file_path)

        log_writer = open(log_file_path, 'a')
       
    # Establishing the RestFul-Flast API at port 3000 on localhost
    app.run(host = '0.0.0.0', port = 3000)