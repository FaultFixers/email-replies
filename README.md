FaultFixers Email Replies Handler
---------------------------------

When a ticket update email is replied to, the reply to updates@faultfixers.com is handled by this repository.

Setup
=====

First, run `pip install -r requirements.txt`

Create these files:

* `service-account-key.json` - should be a service account JSON file created through the Google API Console.
* `.env` - should have the keys `API_ENDPOINT` and `API_AUTHORIZATION_HEADER`.

Run
===

`python run.py`
