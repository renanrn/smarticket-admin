#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, request, jsonify, json
from gerencianet import Gerencianet
import sys

app = Flask(__name__)

@app.route('/')
def hello():
    return 'Bem vindo ao SmarTicket!'

@app.route('/', methods=['POST'])
def hello_post():
    itensJSON = json.loads(request.form['Items'])
    value = itensJSON['value']
    valueS = ('%.2f'%(value)).replace('.','')
    itensJSON['value'] = int(valueS)
    json.dumps(itensJSON)
    print(itensJSON)

    token = request.form['payment_token']
    billingAddress = json.loads(request.form['billing_address'])

    user = json.loads(request.form['user'])
    charge_res = charge(itensJSON)
    charge_id = charge_res['data']['charge_id']
    pay_res = pay(charge_id, token, billingAddress, user)

    return jsonify(response=pay_res,status=200)
    #return 'Hello, {}'.format(upcase(nome)), 200

@app.errorhandler(404)
def page_not_found(error):
    return 'Página não encontrada', 404


def upcase(nome):
    return nome.upper()


options = {
    'client_id': 'Client_Id_0bac5973bde403a31c9618f3877dfcd3182a28a7',
    'client_secret': 'Client_Secret_212163ed29c78a8da6af4a8cbb403fc293202f69',
    'sandbox': True
}

def charge(itensJSON):
    """Realiza o charge para o ingresso do evento escolhido."""        
    gn = Gerencianet(options)
    body = {
        'items': [itensJSON]
    }
    response = gn.create_charge(body=body)
    print(response)
    return response

import dateutil.parser

def pay(charge_id, token, billingAddress, user):
    """Realiza o pagamento para o ingresso do evento escolhido."""        
    date = user['Birth']
    birthParsed = dateutil.parser.parse(date)
    birthFormated = birthParsed.strftime('%Y-%m-%d')

    gn = Gerencianet(options)
    params = {'id': charge_id}

    body = {
            'payment': {
                'credit_card': {
                    'installments': 1,
                    'payment_token': token,
                    'billing_address': {
                        'street': billingAddress['Street'],
                        'number': int(billingAddress['Number']),
                        'neighborhood': billingAddress['Neighborhood'],
                        'zipcode': billingAddress['Zipcode'],
                        'city': billingAddress['City'],
                        'state': billingAddress['State']
                        },
                    'customer': {
                        'name': user['Name'],
                        'email': user['Email'],
                        'cpf': user['Cpf'],
                        'birth': birthFormated,
                        'phone_number': user['PhoneNumber']
                        }
                }
            }
        }
    response = gn.pay_charge(params=params, body=body)
    print(response)
    return response

@app.route('/PagarComandaDividida', methods=['POST'])
def hello_post_pagarcomanda():
    pToken = request.form['payment_token']
    card = json.loads(request.form['card'])
    user = json.loads(request.form['user'])
    billing_addr = json.loads(request.form['billing_address'])
    eventId = card['Event']
    cardId = card['Id']
    itensC = card['Itens']

    new_card = firebase_initialize(cardId, eventId, itensC, user)
    charge_res = chargeNewCard(new_card)
    charge_id = charge_res['data']['charge_id']

    # Logo em seguida vem o pay()
    # Lembrar que no pay devemos inativar a comanda também.
    pay_res = payCardAfterDivide(charge_id, pToken, billing_addr, user)

    return jsonify(response=pay_res, status=200)

#####################  Charge da Comanda com itens em lote  #################################
def chargeComanda(itensC):
    gn = Gerencianet(options)
    print(type(itensC))
    print(itensC)
    sys.exit(0)
    body = {
        'items': [itensC]
    }
    response =  gn.create_charge(body=body)
    print(response)
    return response

import firebase_admin
from firebase_admin import credentials, db

credential = credentials.Certificate(
    "/Users/Renan/Documents/Unisinos/0-PythonServer/SMserviceAccountKey.json")
firebase_admin.initialize_app(credential,{
    'databaseURL': 'https://smarticket-b0cb5.firebaseio.com'
})

def firebase_initialize(cardId,eventId,itensC, userC):
    """Inicializa o Firebase."""

    ref = db.reference('cards')
    card_ref = ref.child(cardId)

    dResult = {item['id']: item['amount'] for item in itensC}
    print(dResult)

    ###### Ajuste em itens para ficar  
    ###### organizado como no banco de dados.
    # dResult = {k: v for i in d2 for k, v in i.items()}

    ######   Trecho para saber por quanto as
    ######   comandas novas serão divididas:
    usersSnapshot = card_ref.child('users').get()    
    divideBy = len(usersSnapshot)
    print(str(divideBy) + ' usuários:')

    ###### Informações sobre usuários
    users = list(usersSnapshot)
    
    ###### Iteração para criar novas comandas 
    ###### para cada usuário contido na comanda anterior.
    userRef = db.reference('users')
    
    for user in users:
        print(user)
        userChild = {str(user) : 'true'}

        new_card_ref = ref.push()
        new_card_key = new_card_ref.key
        new_card_user = {str(new_card_key) : 'true'}
        new_card_ref.set({
                'event'    : int(eventId),
                'itens'    : dResult,
                'status'   : 'active',
                'type'     : 'Particular',
                'users'    : userChild,
                'divideBy'  : divideBy,
                'origin'    : cardId
        })
        
        userUpdate = userRef.child(user)
        cardsUser = userUpdate.child('cards').get()

        if(type(cardsUser)== list):
            cardsUser.append(new_card_user)
        elif(type(cardsUser)== dict):
            cardsUser.update(new_card_user)

        if(user == str(userC['Id'])):
            nova_card = new_card_ref.get()

        userUpdate.update({
            'cards' : cardsUser
        })

    card_ref.update({
        'status' : 'inactive'
    })

    return nova_card

#####################  Charge da Comanda com itens em lote  #################################
def chargeNewCard(new_card):
    """Realiza o charge somente para a comanda DIVIDIDA do usuário que solicitou o fechamento."""    
    gn = Gerencianet(options)    
    ref = db.reference('itens')    
    print(new_card)
    itens_new_card = new_card['itens']
    divideBy = new_card['divideBy']

    itens = []
    ## Dentro do laço abaixo eu itero cada item atualizando o valor
    # final dividindo pelo que está armazenado em divideBy:
    for itemKey, amount in itens_new_card.items():
        itemRef = ref.child(itemKey)
        item = itemRef.get()

        itName = item['name']
        itPrice = item['price']

        itPriceDivided = itPrice / divideBy
        itPriceDivided = '%.2f'%(itPriceDivided)

        itemPrecoDividido = str(itPriceDivided).replace('.','')
        dicItem = {
            'name' : itName,
            'value' : int(itemPrecoDividido),
            'amount' : amount
        }
        itens.append(dicItem)

    print(itens)

    body = {
        'items': itens
    }
    response =  gn.create_charge(body=body)
    print(response)
    return response

def payCardAfterDivide(charge_id, token, billingAddress, user):
    """Realiza o pagamento para a comanda DIVIDIDA recém finalizada do usuário que finalizou."""        
    date = user['Birth']
    print(date)
    birthParsed = dateutil.parser.parse(date)
    birthFormated = birthParsed.strftime('%Y-%m-%d')

    gn = Gerencianet(options)
    params = {'id': charge_id}

    body = {
            'payment': {
                'credit_card': {
                    'installments': 1,
                    'payment_token': token,
                    'billing_address': {
                        'street': billingAddress['Street'],
                        'number': int(billingAddress['Number']),
                        'neighborhood': billingAddress['Neighborhood'],
                        'zipcode': billingAddress['Zipcode'],
                        'city': billingAddress['City'],
                        'state': billingAddress['State']
                        },
                    'customer': {
                        'name': user['Name'],
                        'email': user['Email'],
                        'cpf': user['Cpf'],
                        'birth': birthFormated,
                        'phone_number': user['PhoneNumber']
                        }
                }
            }
        }
    response = gn.pay_charge(params=params, body=body)
    print(response)
    return response
