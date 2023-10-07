from faker import Faker
import json
from PIL import Image
from bs4 import BeautifulSoup
import requests
import time
import os
import pickle
from dotenv import load_dotenv
import secrets
from cryptography.fernet import Fernet
import base64
import mimetypes
from random import randint
from moviepy.editor import VideoFileClip
from functools import wraps

load_dotenv()

USERNAME = os.getenv("THREADS_USERNAME")
PASSWORD = os.getenv("THREADS_PASSWORD")


class Constants:
    BASE_URL = "https://www.threads.net"
    LOGIN_ENDPOINT = "/api/v1/web/accounts/login/ajax/"
    CREATE_SINGLE_MEDIA_THREAD_ENDPOINT = "/api/v1/media/configure_text_post_app_feed/"
    CREAET_SIDECAR_MEDIA_THREAD_ENDPOINT = (
        "/api/v1/media/configure_text_post_app_sidecar/"
    )
    CREATE_TEXT_ONLY_THREAD_ENDPOINT = "/api/v1/media/configure_text_only_post/"
    GRAPHQL_ENDPOINT = "/api/graphql"

    LOGIN_X_ASB_ID = "129477"
    LOGIN_X_IG_APP_ID = "238260118697367"

    DOC_IDS = {
        "LIKE": "6163527303756305",
        "UNLIKE": "6574229129305381",
        "DELETE": "9722027491203611",
        "REPOST": "6590225731000123",
        "UNREPOST": "6614497188614962",
        "FOLLOW": "6520187621436833",
        "UNFOLLOW": "6419596478124270",
        "BLOCK": "7159968810697379",
        "UNBLOCK": "6572924756096893",
        "MUTE": "6464128523654160",
        "UNMUTE": "6543391969109516",
        "GET_NOTIFICATION": "10009082599166431",
        "MARK_NOTIFICATIONS_READ": "6163527303756305",
    }

    BASIC_HEADERS = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "en-US,en;q=0.9",
        "cache-control": "no-cache",
        "dpr": "1",
        "pragma": "no-cache",
        "sec-ch-prefers-color-scheme": "dark",
        "sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
        "sec-ch-ua-full-version-list": '"Google Chrome";v="117.0.5938.149", "Not;A=Brand";v="8.0.0.0", "Chromium";v="117.0.5938.149"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-model": '""',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-platform-version": '"15.0.0"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "viewport-width": "958",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Origin": "https://www.threads.net",
        "X-ASBD-ID": "129477",
        "X-FB-LSD": "NjppQDEgONsU_1LCzrmp6q",
        "X-IG-App-ID": "238260118697367",
    }


class Threads:
    """Threads API wrapper for Python 3.9+ (unofficial)

    This class provides methods to interact with the Threads API, including logging in, posting, liking, deleting, replying, quoting, reposting, and more.
    """

    def __init__(self, username=None, password=None):
        """Initializes a new instance of the Threads class.

        Args:
        username (str): The username to use for authentication.
        password (str): The password to use for authentication.
        """
        self.__session = requests.Session()
        self.username = username
        self.password = password
        self.__timestamp = int((time.time() * 1000))
        self.authenticated = False
        __key = os.getenv("FERNET_KEY")

        self.__cipher_suite = Fernet(f"{__key}".encode())

    def login_required(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            if os.path.exists("encrypted_cookies.pkl"):
                self.__session.cookies = self.__get_cookies()

                self.authenticated = True

            if not self.authenticated:
                print("I am not authenticated")
                if self.username and self.password:
                    self.login()
                else:
                    raise PermissionError("Login required to access this method")
            return func(self, *args, **kwargs)

        return wrapper

    def __send_request_with_auth(self, method, url, headers, **kwargs):
        cookies = self.__get_cookies()
        self.__session.cookies.update(cookies)
        response = self.__session.request(method, url, headers=headers, **kwargs)
        response.raise_for_status()
        self.__encrypt_cookies(self.__session.cookies)
        return response

    def __send_request_without_auth(
        self,
        method,
        endpoint,
        headers=Constants.BASIC_HEADERS,
        **kwargs,
    ):
        response = self.__session.request(method, endpoint, headers=headers, **kwargs)
        response.raise_for_status()
        return response

    def __encrypt_cookies(self, cookies):
        with open("encrypted_cookies.pkl", "wb") as f:
            pickle.dump(cookies, f)

    def __get_cookies(self):
        with open("encrypted_cookies.pkl", "rb") as f:
            cookies = pickle.load(f)
            self.__session.cookies.update(cookies)
            return cookies

    def __get_cookie_item(self, cookie_name):
        cookie = self.__get_cookies()
        return cookie.get(cookie_name, "")

        # return cookie.split(f"{cookie_name}=")[1].split(";")[0]

    @login_required
    def __extract_fb_dtsg(self):
        try:
            response = self.__send_request_with_auth(
                url=Constants.BASE_URL,
                method="GET",
                cookies=self.__get_cookies(),
                headers=Constants.BASIC_HEADERS,
            )

            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            fb_dtsg = json.loads(soup.find("script", {"id": "__eqmc"}).get_text())["f"]
            return fb_dtsg
        except Exception as e:
            print("Error:", e)
            return None

    def __get_fb_dtsg(self):
        fb_dtsg = self.__get_cookie_item("fb_dtsg") or self.__extract_fb_dtsg()
        if fb_dtsg:
            self.__session.cookies.update({"fb_dtsg": fb_dtsg})
            self.__encrypt_cookies(self.__session.cookies)
        return fb_dtsg

    def __get_media_dimensions(self, file_path):
        try:
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type.startswith("image"):
                with Image.open(file_path) as img:
                    return img.size
            elif mime_type.startswith("video"):
                with VideoFileClip(file_path) as video:
                    return video.size
            else:
                raise ValueError("Unsupported media type.")
        except Exception as e:
            print(e)
            return 500, 500

    def __upload_image(
        self,
        media_path,
        supported_types=["image", "video"],
        is_sidecar=False,
    ):
        if not os.path.exists(media_path):
            print("The path provided is not a valid file path.")
            exit()
        mime_type, _ = mimetypes.guess_type(media_path)

        if not mime_type or mime_type.split("/")[0] not in supported_types:
            print("The file type is not supported.")
            exit()

        media_type = "photo" if mime_type.startswith("image") else "video"

        with open(media_path, "rb") as file:
            media_data = file.read()

        width, height = self.__get_media_dimensions(media_path)
        sidecar = "1" if is_sidecar else "0"
        timestamp = int((time.time() * 1000))

        X_INSTAGRAM_RUPLOAD_PARAMS = {
            "is_sidecar": "1" if is_sidecar else "0",
            "is_threads": "1",
            "media_type": 1 if media_type == "photo" else 2,
            "upload_id": timestamp,
            "upload_media_height": height,
            "upload_media_width": width,
        }
        if media_type == "video":
            X_INSTAGRAM_RUPLOAD_PARAMS["extract_cover_frame"] = "1"

        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "content-type": mime_type,
            "dpr": "1",
            "offset": "0",
            "pragma": "no-cache",
            "sec-ch-prefers-color-scheme": "dark",
            "sec-ch-ua": '"Google Chrome";v="117", "Not;A=Brand";v="8", "Chromium";v="117"',
            "sec-ch-ua-full-version-list": '"Google Chrome";v="117.0.5938.149", "Not;A=Brand";v="8.0.0.0", "Chromium";v="117.0.5938.149"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"15.0.0"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "viewport-width": "1280",
            "x-entity-length": str(os.path.getsize(media_path)),
            "x-entity-name": f"fb_uploader_{timestamp}",
            "x-entity-type": mime_type,
            "x-instagram-rupload-params": json.dumps(X_INSTAGRAM_RUPLOAD_PARAMS),
            "Referer": "https://www.threads.net/@topacipolta._gnarly_",
            "Referrer-Policy": "origin-when-cross-origin",
        }

        URL = f"https://www.threads.net/rupload_ig{media_type}/fb_uploader_{timestamp}"
        response = self.__send_request_with_auth(
            url=URL,
            method="POST",
            headers={**Constants.BASIC_HEADERS, **headers},
            data=media_data.decode("latin-1"),
        )
        print(response.json())

        response.raise_for_status()
        return timestamp

    def __get_postid(self):
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
        id = 0
        shortcode = self.get_shortcode()
        print(shortcode)
        for char in shortcode:
            id = (id * 64) + alphabet.index(char)
        print(id)
        return str(id)

    @login_required
    def get_user_id(self, username):
        addional_headers = {
            "cookie": f"mid={self.__get_cookie_item('mid')}; csrftoken={self.__get_cookie_item('csrftoken')}; ds_user_id={self.__get_cookie_item('ds_user_id')}; sessionid={self.__get_cookie_item('sessionid')};",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
        }

        response = self.__send_request_with_auth(
            method="GET",
            url=f"https://www.instagram.com/web/search/topsearch/?query={username}",
            headers={**Constants.BASIC_HEADERS, **addional_headers},
        )
        for item in response.json().get("users"):
            if item["user"]["username"] == username:
                return item["user"]["pk"]
        return None

    @login_required
    def __perform_action(self, variables, doc_id, action_name):
        fb_dtsg = self.__get_fb_dtsg()

        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-ig-app-id": "238260118697367",
            "x-instagram-ajax": "0",
            "Referer": "https://www.threads.net/",
            "Referrer-Policy": "origin-when-cross-origin",
        }

        data = {
            "fb_dtsg": [fb_dtsg],
            "variables": variables,
            "server_timestamps": ["true"],
            "doc_id": [doc_id],
        }

        response = self.__send_request_with_auth(
            method="POST",
            url=Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers={**Constants.BASIC_HEADERS, **addional_headers},
            data=data,
        )

        if not response.json().get("errors"):
            print(f"{action_name} successfully!")
            return True
        else:
            print(f"Failed to {action_name}!")
            return False

    def login(self):
        if not self.username or not self.password:
            raise ValueError("Username and password are required to login")
        csrf_token = self.__send_request_without_auth(
            "GET", Constants.BASE_URL + "/login"
        ).cookies.get("csrftoken", "")

        headers = {
            "x-asbd-id": Constants.LOGIN_X_ASB_ID,
            "x-csrftoken": csrf_token,
            "x-ig-app-id": Constants.LOGIN_X_IG_APP_ID,
            "x-instagram-ajax": "0",
            "Referer": "https://www.threads.net/login",
            "Referrer-Policy": "origin-when-cross-origin",
        }

        payload = {
            "username": self.username,
            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{self.__timestamp}:{self.password}",
            "queryParams": {},
            "optIntoOneTap": "false",
            "csrfmiddlewaretoken": csrf_token,
        }

        response = self.__send_request_without_auth(
            "POST",
            Constants.BASE_URL + Constants.LOGIN_ENDPOINT,
            headers=headers,
            data=payload,
        )

        try:
            if response.json()["authenticated"] == True:
                self.authenticated = True
                print("Logged in successfully!")

                try:
                    headers["x-csrftoken"] = response.cookies["csrftoken"]
                    sessionid = response.cookies.get("sessionid", "")
                    ds_user_id = response.cookies.get("ds_user_id", "")
                    ig_did = response.cookies.get("ig_did", "")
                    mid = response.cookies.get("mid", "")
                    rur = response.cookies.get("rur", "")
                    csrf_token = response.cookies.get("csrftoken", "")
                    custom_cookie = f"sessionid={sessionid}; ds_user_id={ds_user_id}; ig_did={ig_did}; mid={mid}; rur={rur} csrftoken={csrf_token}"
                    print(self.__session.cookies.get_dict())

                    self.__encrypt_cookies(self.__session.cookies)
                except Exception as e:
                    print(e)
                    print("Failed to encrypt session")

            else:
                print("Login failed!")
        except Exception as e:
            print(e)

    @login_required
    def like(self, post_id):
        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-fb-friendly-name": "useBarcelonaLikeMutationLikeMutation",
            "x-fb-lsd": "kUS5ScWK1mWaeRscjA50tY",
            "x-ig-app-id": "238260118697367",
            "Referer": "https://www.threads.net/@saver.bot/post/CyFAoogKvFi",
            "Referrer-Policy": "origin-when-cross-origin",
            # "cookie": f"mid={self.__get_cookie_item('mid')}; csrftoken={self.__get_cookie_item('csrftoken')}; ds_user_id={self.__get_cookie_item('ds_user_id')}; sessionid={self.__get_cookie_item('sessionid')}",
        }

        headers = {**Constants.BASIC_HEADERS, **addional_headers}
        fb_dtsg = self.__get_fb_dtsg()
        # exit()

        payload = {
            "fb_dtsg": [fb_dtsg],
            "variables": [f'{{"media_id":"{post_id}"}}'],
            "server_timestamps": ["true"],
            "doc_id": [f"{Constants.DOC_IDS['LIKE']}"],
        }

        response = self.__send_request_with_auth(
            method="POST",
            url=Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers=headers,
            data=payload,
        )

        print(response.json())

    @login_required
    def unlike(self, post_id):
        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-fb-friendly-name": "useBarcelonaLikeMutationLikeMutation",
            "x-fb-lsd": "kUS5ScWK1mWaeRscjA50tY",
            "x-ig-app-id": "238260118697367",
            "Referer": "https://www.threads.net/@saver.bot/post/CyFAoogKvFi",
            "Referrer-Policy": "origin-when-cross-origin",
        }

        headers = {**Constants.BASIC_HEADERS, **addional_headers}
        fb_dtsg = self.__get_fb_dtsg()
        # exit()

        payload = {
            "fb_dtsg": [fb_dtsg],
            "variables": [f'{{"media_id":"{post_id}"}}'],
            "server_timestamps": ["true"],
            "doc_id": [f"{Constants.DOC_IDS['UNLIKE']}"],
        }

        response = self.__send_request_with_auth(
            "POST",
            Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers=headers,
            data=payload,
        )
        print(response.json())

    @login_required
    def create_thread(
        self,
        message: str,
        media_path: list = [],
        reply_to: str = None,
        quoted_thread_id: str = None,
    ):
        text_post_app_info = (
            {"reply_control": 0, "reply_id": f"{reply_to}"}
            if reply_to
            else {"reply_control": 0}
        )
        if quoted_thread_id:
            text_post_app_info["quoted_post_id"] = quoted_thread_id
        headers = {
            **Constants.BASIC_HEADERS,
            **{
                "x-asbd-id": "129477",
                "x-csrftoken": self.__get_cookie_item("csrftoken"),
                "x-ig-app-id": "238260118697367",
                "x-instagram-ajax": "0",
                "Referer": "https://www.threads.net/",
                "Referrer-Policy": "origin-when-cross-origin",
            },
        }
        if media_path and len(media_path) > 1:
            URL = Constants.BASE_URL + Constants.CREAET_SIDECAR_MEDIA_THREAD_ENDPOINT
            children_metadata = []
            for path in media_path:
                upload_id = self.__upload_image(path, is_sidecar=True)
                children_metadata.append({"upload_id": f"{upload_id}"})
            payload = {
                "caption": message,
                "children_metadata": children_metadata,
                "client_sidecar_id": int((time.time() * 1000)),
                "is_threads": True,
                "text_post_app_info": json.dumps(text_post_app_info),
            }

            data = json.dumps(payload)

        elif media_path and len(media_path) == 1:
            timestamp = self.__upload_image(media_path[0])

            URL = Constants.BASE_URL + Constants.CREATE_SINGLE_MEDIA_THREAD_ENDPOINT

            payload = {
                "caption": message,
                "is_meta_only_post": "",
                "is_paid_partnership": "",
                "text_post_app_info": json.dumps(text_post_app_info),
                "upload_id": timestamp,
            }
            data = payload

        else:
            URL = Constants.BASE_URL + Constants.CREATE_TEXT_ONLY_THREAD_ENDPOINT
            payload = {
                "caption": message,
                "is_meta_only_post": "",
                "is_paid_partnership": "",
                "publish_mode": "text_post",
                "text_post_app_info": json.dumps(text_post_app_info),
                "upload_id": f"{int((time.time() * 1000))}",
            }
            data = payload

        response = self.__send_request_with_auth(
            method="POST",
            url=URL,
            headers=headers,
            data=data,
        )
        print(response.json())

    @login_required
    def delete_thread(self, thread_id):
        fb_dtsg = self.__get_fb_dtsg()

        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-ig-app-id": "238260118697367",
            "x-instagram-ajax": "0",
            "Referer": "https://www.threads.net/",
            "Referrer-Policy": "origin-when-cross-origin",
        }

        body = {
            "fb_dtsg": fb_dtsg,
            "variables": f'{{"media_id":"{thread_id}_52149867531"}}',
            "server_timestamps": "true",
            "doc_id": Constants.DOC_IDS["DELETE"],
        }

        response = self.__send_request_with_auth(
            method="POST",
            url=Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers={**Constants.BASIC_HEADERS, **addional_headers},
            data=body,
        )

        if response.json():
            print("Thread deleted successfully!")
            return True
        else:
            print("Failed to delete thread!")
            return False

    @login_required
    def repost(self, thread_id):
        fb_dtsg = self.__get_fb_dtsg()

        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-ig-app-id": "238260118697367",
            "x-instagram-ajax": "0",
            "Referer": "https://www.threads.net/",
            "Referrer-Policy": "origin-when-cross-origin",
        }
        data = {
            "fb_dtsg": [fb_dtsg],
            "variables": json.dumps({"media_id": thread_id, "repost_context": None}),
            "server_timestamps": ["true"],
            "doc_id": [Constants.DOC_IDS["REPOST"]],
        }

        response = self.__send_request_with_auth(
            method="POST",
            url=Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers={**Constants.BASIC_HEADERS, **addional_headers},
            data=data,
        )

        if not response.json().get("errors"):
            print("Thread reposted successfully!")
            return True
        else:
            print(response.json())
            print("Failed to repost thread!")
            return False

    @login_required
    def unrepost(self, thread_id):
        fb_dtsg = self.__get_fb_dtsg()

        addional_headers = {
            "x-asbd-id": "129477",
            "x-csrftoken": self.__get_cookie_item("csrftoken"),
            "x-ig-app-id": "238260118697367",
            "x-instagram-ajax": "0",
            "Referer": "https://www.threads.net/",
            "Referrer-Policy": "origin-when-cross-origin",
        }
        data = {
            "fb_dtsg": [fb_dtsg],
            "variables": json.dumps({"media_id": thread_id, "repost_context": None}),
            "server_timestamps": ["true"],
            "doc_id": [Constants.DOC_IDS["UNREPOST"]],
        }

        response = self.__send_request_with_auth(
            method="POST",
            url=Constants.BASE_URL + Constants.GRAPHQL_ENDPOINT,
            headers={**Constants.BASIC_HEADERS, **addional_headers},
            data=data,
        )

        if not response.json().get("errors"):
            print("Thread unreposted successfully!")
            return True
        else:
            print(response.json())
            print("Failed to unrepost thread!")
            return False

    @login_required
    def follow(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"target_user_id": user_id}),
            doc_id=Constants.DOC_IDS["FOLLOW"],
            action_name="follow",
        )
        print(action)

    @login_required
    def unfollow(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"target_user_id": user_id}),
            doc_id=Constants.DOC_IDS["UNFOLLOW"],
            action_name="unfollow",
        )
        print(action)

    @login_required
    def block(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"user_id": user_id}),
            doc_id=Constants.DOC_IDS["BLOCK"],
            action_name="block",
        )
        print(action)

    @login_required
    def unblock(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"user_id": user_id}),
            doc_id=Constants.DOC_IDS["UNBLOCK"],
            action_name="unblock",
        )
        print(action)

    @login_required
    def mute(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"author_id": user_id}),
            doc_id=Constants.DOC_IDS["MUTE"],
            action_name="mute",
        )
        print(action)

    @login_required
    def unmute(self, username: str = None, user_id: str = None):
        if not username and not user_id:
            raise ValueError("Either username or user_id is required")
        if username:
            user_id = self.get_user_id(username)
        action = self.__perform_action(
            variables=json.dumps({"author_id": user_id}),
            doc_id=Constants.DOC_IDS["UNMUTE"],
            action_name="unmute",
        )
        print(action)
