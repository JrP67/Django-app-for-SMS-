# SMS Sender (Django \+ SMSGate)

IT 120 – Integrative Programming and Technologies · Group Assignment

## Description

A Django web app that lets a user enter a recipient phone number and a message, validates them, sends the SMS through an SMS gateway, and shows whether the request succeeded. Every attempt is saved to a history page. The app reports **submitted** (the gateway accepted it) separately from **delivered** (confirmed), and never claims delivery without checking.

**SMS provider:** [SMSGate](https://sms-gate.app), a free, open-source Android app that turns a phone into an SMS gateway with a REST API. Messages are sent from the SIM card of the phone running the app. (We use it instead of Twilio because Twilio does not offer free trials in the Philippines.)

**Users:** anyone who needs to send a quick text from a browser. **Purpose:** practice API integration, validation, error handling, and secure credential handling in Django.

## Group members and responsibilities

| Member | Responsibility |
| :---- | :---- |
| Joseph Renanh Polistico | Django project setup, views, URLs, application logic |
| John Paul T. Cabas | UI, forms, validation, user feedback |
| Rica Mae Rojas | SMS provider integration, testing, documentation, demo |

Main features

- SMS form with recipient number, message, and **Send SMS** button  
- Phone validation (international format; local `09…` numbers become `+63…`)  
- Empty or invalid input rejected with clear messages  
- Handling for missing/wrong credentials, network failures, and gateway rejections  
- **Additional features:** live message preview, character and segment counter, sending history, and per-message status check  
- CSRF protection on all forms; credentials only in environment variables

## Technologies

Python 3.10+, Django 5, Requests, python-dotenv, HTML/CSS, SQLite, SMSGate (Android app \+ REST API).

## Project structure

```
sms_project/
├── manage.py
├── requirements.txt
├── .env.example
├── sms_project/        # settings, root URLs
└── sms_app/
    ├── forms.py        # input validation
    ├── phone.py        # phone number cleaning
    ├── services.py     # all gateway calls and error translation
    ├── views.py        # send, history, refresh status
    ├── models.py       # SMSLog
    ├── templates/sms_app/
    ├── static/sms_app/
    └── tests.py
```

## Workflow

1. User opens the app
2. User enters recipient
3. User writes message
4. App validates
5. App submits to the gateway
6. App shows the result and logs it

## Installation and setup

```sh
git clone <your-repo-url>
cd sms_project
python -m venv venv
# Windows: venv\Scripts\activate      macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # Windows: copy .env.example .env
```

Edit `.env` (see next section), then:

```sh
python manage.py makemigrations sms_app
python manage.py migrate
python manage.py runserver
```

Open [http\://127.0.0.1:8000/](http://127.0.0.1:8000/)

## Configuring the SMS provider (SMSGate)

1. On an Android phone with a working SIM, install the SMSGate app from [https\://sms-gate.app](https://sms-gate.app) (APK or releases page). No account is needed.  
2. Open the app, switch **Cloud Server** on, and tap **Online**.  
3. Copy the **username** and **password** shown in the Cloud Server section into `.env` as `SMSGATE_USERNAME` and `SMSGATE_PASSWORD`.  
4. Keep the phone online with the app running while you test. Only text authorized test recipients (yourself and your groupmates).  
5. Never commit `.env` and never show the password in screenshots or the video.

Generate a Django secret key if needed: `python -c "import secrets; print(secrets.token_urlsafe(50))"`

## Running tests

```sh
python manage.py test
```

The automated tests mock the gateway, so they don't send real SMS.

## Manual test results

| Test case | Expected | Result |
| :---- | :---- | :---- |
| Valid number and message | Submitted, status shown | Pass: gateway accepted, shown in history |
| Empty phone number | Validation message | Pass: "Enter the recipient's phone number." |
| Empty message | Validation message | Pass: "Write a message before sending." |
| Invalid phone number | Validation error | Pass: "Start the number with a country code…" (input `111112`) |
| Wrong or missing gateway password | Friendly error, no secrets shown | Pass (missing password): "SMS sending isn't set up yet. Missing settings: SMSGATE_PASSWORD." |
| Internet off | "Couldn't reach the SMS gateway" message | Pass: "Couldn't reach the SMS gateway. Check your internet connection…" |
| Check status after sending | Status updates (e.g. sent / delivered) | Pass: status refreshed to "delivered" |

## Known limitations

- The phone running SMSGate must be online; otherwise messages stay "pending". The cloud server may also take a little while to wake the phone.  
- Normal carrier SMS rates or load apply to messages sent from the phone's SIM.  
- "Sent" means the phone sent it; only "delivered" is confirmation, and it depends on the carrier reporting it.  
- No login: anyone who can open the site can send and see history. Add authentication before any real deployment.  
- Local-number conversion only covers Philippine `09…` numbers.