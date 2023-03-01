import json
from django.conf import settings
import requests
from requests.auth import HTTPBasicAuth
from ...models import User
from ..api_result import ApiResult
from .user_filter import UserFilter as KaonaviUserFilter

END_POINT_URL_BASE = 'https://api.kaonavi.jp/api/v2.0'
SELF_INTRO_SHEET_ID = 20
NONE_AS_DEFAULT_VALUE = None
NAME_FIELD_ID = '284'
BIRTH_PLACE_FIELD_ID = '286'
JOB_DESCRIPTION_FIELD_ID = '287'
CAREER_FIELD_ID = '288'
HOBBY_FIELD_ID = '289'
SPECIALTY_FIELD_ID = '290' # 特技
STRENGTHS_FIELD_ID = '291' # アピールポイント
MESSAGE_FIELD_ID = '292'

class KaonaviConnector:
    def __init__(self):
        self.access_token = self.get_access_token()

    def get_access_token(self):
        response = requests.post(
            f"{END_POINT_URL_BASE}/token",
            auth=HTTPBasicAuth(
                getattr(settings, 'KAONAVI_API_KEY', None),
                getattr(settings, 'KAONAVI_API_SECRET', None),
            ),
            data='grant_type=client_credentials',
            headers={'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'},
        )
        return response.json()['access_token']

    def get_kaonavi_users(self):
        response = requests.get(
            f"{END_POINT_URL_BASE}/members",
            data='grant_type=client_credentials',
            headers={
                'Content-Type': 'application/json',
                'Kaonavi-Token': self.access_token
            },
        )
        return response.json()['member_data']

    def get_self_introduction_sheet(self):
        response = requests.get(
            f"{END_POINT_URL_BASE}/sheets/{SELF_INTRO_SHEET_ID}",
            data='grant_type=client_credentials',
            headers={
                'Content-Type': 'application/json',
                'Kaonavi-Token': self.access_token
            },
        )

        return response.json()

    def get_users(self, params):
        """全社員情報取得"""
        kaonavi_users = KaonaviUserFilter(params, self.get_kaonavi_users()).call()

        if len(kaonavi_users) >= 1:
            formatted_users = []

            for kaonavi_user in kaonavi_users:
                user = User.objects.get(kaonavi_code=kaonavi_user['code'])
                departments = kaonavi_user['department']['names']
                role = next((custom_field for custom_field in kaonavi_user['custom_fields'] if custom_field['name'] == '役職'), NONE_AS_DEFAULT_VALUE)
                formatted_users.append(
                    dict(
                        user_id=user.id,
                        name=kaonavi_user['name'],
                        name_kana=kaonavi_user['name_kana'],
                        headquarters=departments[0] if len(departments) >= 1 else '',
                        department=departments[1] if len(departments) >= 2 else '',
                        group=departments[2] if len(departments) >= 3 else '',
                        role=role['values'][0] if role is not None else '',
                        # 未実装だからコメントアウト
                        details=self.self_introduction_info(kaonavi_user['code'])
                    )
                )
            return ApiResult(success=True, data=formatted_users)
        else:
            return ApiResult(success=False, errors=['社員情報の取得に失敗しました'])

    def get_user(self, user_id, kaonavi_code):
        """カオナビの社員codeに紐づく社員情報取得"""
        kaonavi_user = next((kaonavi_user for kaonavi_user in self.get_kaonavi_users() if kaonavi_user['code'] == kaonavi_code), NONE_AS_DEFAULT_VALUE)
        if kaonavi_user is NONE_AS_DEFAULT_VALUE:
            return ApiResult(success=False, errors=[f"id:{user_id}の社員情報の取得に失敗しました"])
        else:
            departments = kaonavi_user['department']['names']
            formatted_user = dict(
                overview=dict(
                    image='https//path_to_image.com',
                    name=kaonavi_user['name'],
                    name_kana=kaonavi_user['name_kana'],
                    headquarters=departments[0] if len(departments) >= 1 else '',
                    department=departments[1] if len(departments) >= 2 else '',
                    group=departments[2] if len(departments) >= 3 else '',
                ),
                tags=self.tags(kaonavi_user),
                details=self.self_introduction_info(kaonavi_user['code'])
            )
            return ApiResult(success=True, data=formatted_user)

    def tags(self, kaonavi_user):
        years_of_service = f"勤続{kaonavi_user['years_of_service']}"
        role = next((custom_field for custom_field in kaonavi_user['custom_fields'] if custom_field['name'] == '役職'), NONE_AS_DEFAULT_VALUE)
        role = f"役職：{role['values'][0]}" if role is not None else ''
        recruit_category = next((custom_field for custom_field in kaonavi_user['custom_fields'] if custom_field['name'] == '採用区分'), NONE_AS_DEFAULT_VALUE)
        recruit_category = recruit_category['values'][0] if recruit_category is not None else ''
        gender = kaonavi_user['gender']

        return [
            years_of_service,
            role,
            recruit_category,
            gender
        ]

    def self_introduction_info(self, kaonavi_code):
        sheets = self.get_self_introduction_sheet()
        my_sheet = next((sheet for sheet in sheets['member_data'] if sheet['code'] == kaonavi_code), NONE_AS_DEFAULT_VALUE)
        data = dict(
            job_description=dict(
                title='業務内容、役割',
                value=''
            ),
            birth_place=dict(
                title='出身地',
                value=''
            ),
            career=dict(
                title='経歴、職歴',
                value=''
            ),
            hobby=dict(
                title='趣味',
                value=''
            ),
            specialty=dict(
                title='特技',
                value=''
            ),
            strengths=dict(
                title='アピールポイント',
                value=''
            ),
            message=dict(
                title='最後にひとこと',
                value=''
            )
        )

        if my_sheet is NONE_AS_DEFAULT_VALUE:
            return data
        else:
            data['job_description']['value'] = 'ここに自分のシートの業務内容を入れたい'
            data['birth_place']['value'] = 'ここに自分のシートの出身地を入れたい'
            data['career']['value'] = 'ここに自分のシートの経歴を入れたい'
            data['hobby']['value'] = 'ここに自分のシートの趣味を入れたい'
            data['specialty']['value'] = 'ここに自分のシートの特技を入れたい'
            data['strengths']['value'] = 'ここに自分のシートのアピールポイントを入れたい'
            data['message']['value'] = 'ここに自分のシートの最後にひとことを入れたい'
            return data

    def create_or_update_user(self, user, params):
        request_json = self.build_create_or_update_user_json(user, params)
        sheets = self.get_self_introduction_sheet()
        my_sheet = next((sheet for sheet in sheets['member_data'] if sheet['code'] == user.kaonavi_code), NONE_AS_DEFAULT_VALUE)
        if my_sheet is NONE_AS_DEFAULT_VALUE:
            # 自己紹介シートを未作成の場合
            method = 'POST'
            url = f"{END_POINT_URL_BASE}/sheets/{SELF_INTRO_SHEET_ID}/add"
        else:
            # 既に自己紹介シートを作成済の場合
            method = 'PATCH'
            url = f"{END_POINT_URL_BASE}/sheets/{SELF_INTRO_SHEET_ID}"

        response = requests.request(
            method=method,
            url=url,
            headers={
                'Content-Type': 'application/json',
                'Kaonavi-Token': self.access_token,
                # 'Dry-Run': '1' # 1はテスト
            },
            data=request_json
        )

        if response.ok:
            return ApiResult(success=True)
        else:
            return ApiResult(success=False)

    def build_create_or_update_user_json(self, user, params):
        obj = {
            "member_data": [
                {
                    "code": user.kaonavi_code,
                    "records": [
                        {
                            "custom_fields": [
                                {"id": NAME_FIELD_ID, "values": [user.username]},
                                {"id": BIRTH_PLACE_FIELD_ID, "values": [params['birth_place']]},
                                {"id": JOB_DESCRIPTION_FIELD_ID, "values": [params['job_description']]},
                                {"id": CAREER_FIELD_ID, "values": [params['career']]},
                                {"id": HOBBY_FIELD_ID, "values": [params['hobby']]},
                                {"id": SPECIALTY_FIELD_ID, "values": [params['specialty']]},
                                {"id": STRENGTHS_FIELD_ID, "values": [params['strengths']]},
                                {"id": MESSAGE_FIELD_ID, "values": [params['message']]}
                            ]
                        }
                    ]
                }
            ]
        }
        return json.dumps(obj)