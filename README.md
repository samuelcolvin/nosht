nosht
========

[![Build Status](https://travis-ci.com/samuelcolvin/nosht.svg?branch=master)](https://travis-ci.com/samuelcolvin/nosht)
[![codecov](https://codecov.io/gh/samuelcolvin/nosht/branch/master/graph/badge.svg)](https://codecov.io/gh/samuelcolvin/nosht)


To set up for a new instance:
* facebook login via facebook developer
* google maps key and google oauth 2.0 key both form google developer console
* AWS, see below

Stripe doesn't need any env var setup, just the api keys on the company


## AWS setup

Create an S3 bucket, you'll need to name it the same as the domain you want to access it from.

Create an IAM role with the following policy 
**(remember to change the bucket name from `bucketname.example.com` to your bucket name)**.

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
                "arn:aws:s3:::bucketname.example.com"
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
                "arn:aws:s3:::bucketname.example.com/*"
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


    heroku addons:create heroku-postgresql:hobby-dev -a $HEROKU_APP
    heroku addons:create rediscloud:30 -a $HEROKU_APP
