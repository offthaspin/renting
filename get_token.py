import requests
from requests.auth import HTTPBasicAuth

consumer_key = "RfoU0DNgOTrehcoRPgMdbhGzKMNAjCrgvMAjaYny4pclLnA2"
consumer_secret = "YbLFo4q51WJFZyQxTcknzXIL1nEr4B9pefPVWTnB1qDf7jvoa2atQQm6AYH0D5pu"

url = "https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials"

response = requests.get(url, auth=HTTPBasicAuth(consumer_key, consumer_secret))
print(response.json())
