nosht
=====
[![CI](https://github.com/samuelcolvin/nosht/workflows/ci/badge.svg?event=push)](https://github.com/samuelcolvin/nosht/actions?query=event%3Apush+branch%3Amaster+workflow%3Aci)
[![codecov](https://codecov.io/gh/samuelcolvin/nosht/branch/master/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/nosht)


# Summary

Nosht is an event ticketing platform originally built for [The Hands Up Foundation](https://handsupfoundation.org/)
which is available under an open source license (MIT) for use by anyone.

If you have any questions please create an issue on github.

# Technical Summary

The platform is built using the following tools:
* the server side is built using the **aiohttp** web framework and **python 3**
* the main database is **postgres** with **redis** as a cache and queuing system
* the front end uses **react** and "create react app"
* the system is deployed at present using **heroku**'s container runtime although nothing in the system should rely
  on heroku
* **AWS SES** is used to send emails
* **AWS S3** is used to store user uploaded images
* **Cloudflare** is used as a reverse-proxy and CDN for all traffic including S3
* **sentry/raven** collects error reports
* **Stripe** does card payments

# Deployment & Setup

Install the following:
* python3.6
* [heroku cli](https://devcenter.heroku.com/articles/heroku-cli)
* [docker](https://docs.docker.com/cs-engine/1.12/)

## Heroku Setup

Create an app on heroku (make sure to choose the most appropriate region), add the following add-ons
* Heroku Postgres - choose a size appropriate for your needs
* Redis Cloud - the free 30MB option should be sufficient
* Papertail - the smallest (free) option should be sufficient

Export an environment variable identifying your heroku app:

```bash
export HEROKU_APP=<name of your app>
```

Make sure your heroku CLI can connect to heroku:

```bash
heroku ps -a $HEROKU_APP
```

(you won't see much but the command should pass)

You'll need to set the following config (environment) variables in heroku:
* `APP_AUTH_KEY` can be set by simply running `make heroku-set-auth-key`, random key, keep is secret
* `APP_AWS_ACCESS_KEY` key from AWS, see "AWS Setup" below
* `APP_AWS_SECRET_KEY` key from AWS, see "AWS Setup" below
* `APP_S3_BUCKET` name of the S3 bucket your using eg. `events-images.example.org`, see "AWS Setup" below
* `APP_S3_DOMAIN` root url for the S3 bucket eg. `https://events-images.example.org`, see "AWS Setup" below
* `APP_AWS_SES_WEBHOOK_AUTH` basic auth password for SES webhooks
* `APP_S3_PREFIX` prefix to use for all files in S3, eg. `prod`
* `APP_FACEBOOK_SIW_APP_SECRET` key from facebook, see "Facebook Setup" below
* `APP_GOOGLE_MAPS_STATIC_KEY` key for google maps, see "Google Setup" below
* `APP_GOOGLE_SIW_CLIENT_KEY` google signin with key, see "Google Setup" below
* `APP_GRECAPTCHA_SECRET` google recaptcha key, see "Google Setup" below
* `RAVEN_DSN` DSN from sentry/raven, see "Sentry Setup" below
* `APP_DONORFY_API_KEY` API key for donorfy integration
* `APP_DONORFY_ACCESS_KEY` API "access key" for donorfy integration
* `APP_CSP_IMAGE_SOURCE` to something like `https://events-images.example.org` to allow images to show

## Build and Deploy

With Heroku's container runtime you build docker images for you app locally, push them to heroku, then deploy those
images.

First of all, clone the nosht code

    git clone git@github.com:samuelcolvin/nosht.git
    cd nosht

Before you can build the image you'll need to create a few static files which are built into the images:

these files are kept in a directory named `deploy-settings-<heroku-app-name>`, eg. if your app on heroku is called
`example-events`, the directory should be called `deploy-settings-example-events`

It should look like

```
deploy-settings-example-events/
├── .env.production
└── favicons
    ├── android-chrome-192x192.png
    ├── android-chrome-256x256.png
    ├── apple-touch-icon.png
    ├── browserconfig.xml
    ├── favicon-16x16.png
    ├── favicon-32x32.png
    ├── favicon.ico
    ├── logo.png
    ├── mstile-150x150.png
    ├── safari-pinned-tab.svg
    └── site.webmanifest
```

You can generate most of the files for `favicons/` using [this helpful service](https://realfavicongenerator.net/).
The only exception is `logo.png` which should be a 380x150px logo for your service.

`.env.production` provides production settings for the "create react apps" build, it should contain the following

```
REACT_APP_SITE_NAME='<the name of your service/company>'
REACT_APP_THEME_COLOUR='company hex colour, should match favicons/browserconfig.xml, eg. "016997"'
REACT_APP_COPYRIGHT_STATEMENT='© copyright statement for the footer'
REACT_APP_GOOGLE_MAPS_KEY='<public google maps key, see below>'
REACT_APP_GOOGLE_SIW_CLIENT_KEY='<google signin with client key, see below>'
REACT_APP_FACEBOOK_SIW_APP_ID='<facebook signin with app id, see below>'
REACT_APP_RECAPTCHA_KEY='<google recaptcah public key>'
REACT_APP_SENTRY_DSN='<sentry dsn for js error tracking>'
REACT_APP_GA_TRACKING_ID='<tracking id for google analytics>'
```

Log in to heroku's container registry

    heroku container:login

With `deploy-settings-<heroku-app-name>` setup, you can build and deploy your images:

    make heroku-push

will build the docker images and push them to heroku,

    make heroku-release

will release those images, the following should now show you both the worker and web dyno's running

```bash
heroku ps -a $HEROKU_APP
```

However you'll likely get a 500 error if you try to go to your site.

To create database tables run

```bash
heroku run "./run.py reset_database" --type=worker -a $HEROKU_APP
```

and to create a company:

```bash
heroku run "./run.py patch create_new_company --live" --type=worker -a $HEROKU_APP
```

You can see other commands available by running just `./run.py` or `./run.py patch`.

## Third Party Providers

### AWS Setup

Create an S3 bucket, you'll need to name it the same as the domain you want to access it from. Eg. name
the bucket `event-images.example.org` to a access files at `https://event-images.example.org/...`.

Create an IAM role with the following policy 
**(remember to change the bucket name from `bucketname.example.org` to your bucket name)**.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::bucketname.example.org"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:DeleteObject",
                "s3:GetObjectAcl",
                "s3:PutObjectAcl"
            ],
            "Resource": [
                "arn:aws:s3:::bucketname.example.org/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "ses:*"
            ],
            "Resource": "*"
        }
    ]
}
```

Go to SES and setup a sending domain. You either need to set it up in the `eu-west-1` region
or change the region `aws_region` setting.

#### SES webhooks

Notifications of email events (delivery, opening, clicks etc.) are recorded in nosht via webhooks from SES.

To setup these webhooks:
1. log into AWS > SES > Configuration Sets
1. Create a Configuration Set called exactly `nosht`.
1. Add a destination of type "SNS", call it something like `nosht-cloudwatch` and check all Event types,
  choose "Create an SNS topic" and call it `nosht-emails` or similar.
1. Move in the AWS console to SNS, go to topics and you should see the topic you just created.
1. Hit "create subscription", choose the type as "https" and enter the url as 
  `https://{APP_AWS_SES_WEBHOOK_AUTH}@events.example.org/api/ses-webhook/`, where `APP_AWS_SES_WEBHOOK_AUTH` is
  is the basic auth username and password which will also be set in Heroku, it needs a colon in, eg.
  `user:randompassword`.
1. If the platform is up and running when you create the subscription (and you've done it right) it should get approved
  immediately, if not you'll need to create another one or retry once the platform is running
1. Currently emails and email events aren't displayed anywhere in the system, but they're saved to the database
  for manual checking or future display.

To set from AWS:

* heroku config `APP_AWS_ACCESS_KEY`
* heroku config `APP_AWS_SECRET_KEY`
* heroku config `APP_S3_BUCKET`
* heroku config `APP_S3_DOMAIN`
* heroku config `APP_AWS_SES_WEBHOOK_AUTH`

### Cloudflare Setup

Add a CNAME record for the main system (probably `events.`)

    CNAME    events          events.example.org.herokudns.com

(or whatever domain heroku gives you)

Add a CNAME record for the S3 subdomain, eg.

    CNAME    event-images    events-images.example.org.s3.amazonaws.com

### Facebook Setup

Search for "facebook developer dashboard", wade through their horrible interface until you've created an app
to "Let people log in with their Facebook account", you can then go to settings > basic to get the 
"App ID" and "App Secret". 

To set from Facebook:

* heroku config `APP_FACEBOOK_SIW_APP_SECRET`
* `.env.production` > `REACT_APP_FACEBOOK_SIW_APP_ID`

### Google Setup

Lots of keys need for different bits of google's integration:

Go to https://console.developers.google.com, make sure your on the right project, or create a new one
(you'll need billing to be setup for all the keys to work correctly), go to credentials:
* set up an "API Key" with permission for "Maps JavaScript API" and "Geocoding API", 
  restrict it to your domain using "HTTP referres", use this for `REACT_APP_GOOGLE_MAPS_KEY`.
* set up an "API Key" with permission for "Maps Static API", use this for `APP_GOOGLE_MAPS_STATIC_KEY`.
* set up an "OAuth client ID", set the authorised origin, set `REACT_APP_GOOGLE_SIW_CLIENT_KEY` to the Client ID
  and `APP_GOOGLE_SIW_CLIENT_KEY` to the "Client secret".

Search "google recaptcha" and setup a V2 key for your site, set the allowed domains, 
set `REACT_APP_RECAPTCHA_KEY` to the "Site key", set `APP_GRECAPTCHA_SECRET` to the "Secret key".

Go to google analytics, set up a new property, take the tracking ID and copy it into `REACT_APP_GA_TRACKING_ID`.

To set from Google:

* heroku config `APP_GOOGLE_MAPS_STATIC_KEY`
* heroku config `APP_GOOGLE_SIW_CLIENT_KEY`
* heroku config `APP_GRECAPTCHA_SECRET`
* `.env.production` > `REACT_APP_GOOGLE_MAPS_KEY`
* `.env.production` > `REACT_APP_GOOGLE_SIW_CLIENT_KEY`
* `.env.production` > `REACT_APP_RECAPTCHA_KEY`
* `.env.production` > `REACT_APP_GA_TRACKING_ID`

### Sentry Setup

Go to https://sentry.io, create a new account, organisation or project and copy the DSN.

To set from Sentry:

* heroku config `RAVEN_DSN`
* `.env.production` > `REACT_APP_SENTRY_DSN`

### Stripe Setup

Setup the the stripe account, create a webhook with the following settings:
* event types, just `payment_intent.succeeded`
* url `https://events.example.org/api/stripe/webhook/`

Enter the stripe public key, stripe secret key and stripe webhook secret into the company edit form.

# Setting up a local testing environment

You'll need to run something like the following and use your initiative if things fail, add an issue to github
if you get confused

```bash
pwd  # should be /.../nosht
virtualenv -p `which python3.6` env
source env/bin/active
make install
cd js/
yarn
cd ..
```

To run tests locally, you should be able to simply run

```bash
make
```

## Development Mode

(Requires the same dependencies as above as well as postgresql and redis, and of course for the code to be cloned.)

To run the front end in development mode

```bash
cd js/
yarn start
```

The js dev server will proxy requests through to the backend so you'll also need to run the server at the
same time in a different window.

Before running this you'll probably need to set up some of the environment variables mentioned above for the system
to run properly.

Here's a very basic file structure to get your development setup working, `avtivate.dev.sh`:

```bash
export APP_AWS_ACCESS_KEY='...'
export APP_AWS_SECRET_KEY='...'
export APP_S3_BUCKET='bucket.example.com'
export APP_S3_PREFIX='local'
export APP_S3_DOMAIN='https://bucket.example.com'

source env/bin/activate
```

```bash
cd nosht/
source activate.dev.sh
cd py/
# This creates a demo company for testing
./run.py patch create_demo_data --live
./run.py web
```

(or change the last command to `adev runserver web/main.py` to reload the system on file changes.)

If you want the worker running as well you'll also run (from another terminal)

```bash
cd nosht/
source activate.dev.sh
cd py/
./run.py worker
```

## Docker Testing

Instead of running each process/component independently you can also develop using docker to run your application,
this will result in a much slower feedback but may be easier in some circumstances:

Simply run

```bash
make docker-dev
```

And then `make docker-dev-stop` once you've finished to stop the server.
