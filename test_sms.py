import os
from dotenv import load_dotenv
load_dotenv()
import africastalking

username = os.getenv("AFRICASTALKING_USERNAME")
api_key = os.getenv("AFRICASTALKING_API_KEY")

africastalking.initialize(username, api_key)
sms = africastalking.SMS

response = sms.send("Test message from Rentana", ["+254712345678"], sender_id=os.getenv("AT_SENDER","Rentana"))
print(response)
