import boto3
from moto import mock_s3
from moto.core import patch_client

from flask import Flask, request
from werkzeug.utils import secure_filename
import os
import datetime
from hashlib import md5
import unittest
import logging

s3_client = boto3.client("s3")

USER_PROFILE_PICTURES_S3_BUCKET = "a-image-bucket-name"

def upload_file_to_s3(file, bucket_name, filename, acl="public-read"):
    try:
        s3_client.upload_fileobj(file, bucket_name, filename, ExtraArgs={"ACL": acl, "ContentType": file.content_type})
    except Exception as e:
        logging.error(str(e))
        raise e
    return f"https://s3.eu-west-1.amazonaws.com/{USER_PROFILE_PICTURES_S3_BUCKET}/{filename}"


app = Flask(__name__)


@app.post("/users/me/profile_picture")
def upload_user_profile_picture():
    if "image" not in request.files:
        return 400
    file = request.files["image"]
    if file:
        if file.filename == "":
            return 400
        file.filename = secure_filename(file.filename)
        file_extension = file.filename.split(".")[-1]
        output = upload_file_to_s3(
            file, USER_PROFILE_PICTURES_S3_BUCKET, f"{md5('some-user@email.com'.encode()).hexdigest()}.{file_extension}"
        )
        return output, 200
    else:
        return 400


class _TestCase(unittest.TestCase):
    def setUp(self):
        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SECURITY_TOKEN"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

        # self.create_entries()
        app.testing = True
        app.config["JWT_ACCESS_TOKEN_EXPIRES"] = datetime.timedelta(minutes=1)
        app.config["JWT_REFRESH_TOKEN_EXPIRES"] = datetime.timedelta(minutes=1)
        app.config["FLASK_SECRET_KEY"] = "TestSecretKey"
        self.test_client = app.test_client()
        self.default_email = "user_1@mail.test"
        self.default_id = 1


@mock_s3
class Tests(_TestCase):

    new_image_url = (
        "https://s3.eu-west-1.amazonaws.com/a-image-bucket-name/14b4423f7ed304018dddb7f07c542e60.jpg"
    )

    def _setup_s3(self):
        # Connecting to mocked s3 instance
        conn = boto3.resource("s3", region_name="us-east-1")
        # We need to create the bucket since this is all in Moto's 'virtual' AWS account
        conn.create_bucket(Bucket=USER_PROFILE_PICTURES_S3_BUCKET)
        # Patching the s3 client used in the route
        patch_client(s3_client)

    def test_upload_image(self):
        self._setup_s3()

        data = {"image": (open("test_image.jpg", "rb"), "test_image.jpg")}
        response = self.test_client.post("/users/me/profile_picture", data=data, content_type="multipart/form-data")
        logging.debug(response)
        logging.debug(response.text)
        # Burned down test, not testing anything related to database, just want to see if the function returns normally without a boto error.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, self.new_image_url)

