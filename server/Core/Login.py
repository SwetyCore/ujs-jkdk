import base64
import re
import time
import requests
from lxml import etree

from .log1 import l
import json
import execjs


class Login:
    def __init__(self, config):
        self.config = config

    def __GetcaptchaWord(self, pic):
        l.info('识别验证码...')
        request_url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

        # config = json.load(open(self.config, 'r'))
        apikey = self.config.apikey
        secretkey = self.config.secretkey

        host = f'https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials&client_id={apikey}&client_secret={secretkey}'
        response = requests.get(host)

        img = base64.b64encode(pic)

        params = {"image": img}
        access_token = response.json()['access_token']
        request_url = request_url + "?access_token=" + access_token
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        response = requests.post(request_url, data=params, headers=headers)
        word = response.json()['words_result'][0]['words']
        # 去除空格
        while ' ' in word:
            word = word.replace(' ', '')
        l.info(f'验证码为:{word}')
        return word

    def __getcaptcha(self, captchaApi):
        '''
        请求验证码
        :param captchaApi: 请求地址
        :return: byte类型的图片
        '''
        l.info('开始请求验证码')
        response = self.ses.get(captchaApi)
        return response.content

    def __getargv(self, html):
        '''
        获取登录表单里面的两个参数和密码加密参数
        :param html: 网页代码
        :return: list[lt,execution,密码加密的key]
        '''
        key = re.findall(r'var pwdDefaultEncryptSalt = "(.*?)";', html)[0]

        document = etree.HTML(html)
        lt= document.xpath('''//input[@name="lt"]/@value''')
        execution=document.xpath('''//input[@name="execution"]/@value''')

        # soup = BeautifulSoup(html, 'html.parser')
        # form = soup.find_all('form', id='casDynamicLoginForm')
        # formstr = str(form[0])
        # lt = re.findall(r'<input name="lt" type="hidden" value="(.*?)"/>', formstr)[0]
        # execution = re.findall(r'<input name="execution" type="hidden" value="(.*?)"/>', formstr)[0]
        # l.info(f'lt={lt}\texecution={execution}\tpwdDefaultEncryptSalt={key}')




        return [lt, execution, key]

    def __encrypt(self, password, key):
        l.info('加密密码....')
        '''
        加密密码
        :param password: 初始密码
        :return: 加密后的
        '''
        vm = execjs.compile(open('Core/js/jiami.js').read() + open('Core/js/encrypt.js').read())
        js = '_etd2("{0}", "{1}")'.format(password, key)
        password = vm.eval(js)
        return password

    def __loginPost(self, loginapi, username, passwordEncrypt):
        l.info('提交登录请求...')
        '''
        提交登录表单部分
        :param loginapi: 提交表单的地址
        :param username: 用户名
        :param passwordEncrypt: 加密后的密码
        :return: 页面的response
        '''
        data = {
            'username': username,
            'password': passwordEncrypt,
            'captchaResponse': self.captchaWord,
            'lt': self.lt,
            'dllt': 'userNamePasswordLogin',
            'execution': self.execution,
            '_eventId': 'submit',
            'rmShown': 1
        }

        response = self.ses.post(url=loginapi, data=data, )
        return response

    def Login(self, username, password):
        """
        登录方法
        :param username: 学号
        :param password: 密码
        :return: 成功返回会话session,失败返回None.
        """
        captchaApi = 'https://pass.ujs.edu.cn/cas/captcha.html'
        loginapi = 'https://pass.ujs.edu.cn/cas/login'
        self.ses = requests.session()
        self.ses.headers = {
            'Host': 'pass.ujs.edu.cn',
            'Referer': 'https://pass.ujs.edu.cn/cas/login',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.193 Safari/537.36 Edg/86.0.622.68'
        }
        response = self.ses.get(loginapi)
        try:
            html = response.content.decode("UTF-8")
        except:
            html = response.content.decode("GBK")

        pic = self.__getcaptcha(captchaApi)
        self.captchaWord = self.__GetcaptchaWord(pic)

        while len(self.captchaWord) != 4:
            l.warn('验证码识别失败,重试中...')
            time.sleep(1)
            pic = self.__getcaptcha(captchaApi)
            try:
                self.captchaWord = self.__GetcaptchaWord(pic)
            except:
                self.captchaWord=''

        argvs = self.__getargv(html)
        self.lt = argvs[0][0]
        self.execution = argvs[1][0]
        self.key = argvs[2]

        passwordEncrypt = self.__encrypt(password=password, key=self.key)

        # 提交表单
        l.info('提交登录请求...')
        response = self.__loginPost(loginapi=loginapi, username=username, passwordEncrypt=passwordEncrypt)
        l.info(str(response.status_code))
        try:
            responseHtml = response.content.decode("UTF-8")
        except:
            responseHtml = response.content.decode("GBK")
        if '个人资料' in responseHtml:
            l.info('登录成功!!')
            return self.ses
        elif '您提供的用户名或者密码有误' in responseHtml:
            l.warn('账号密码错误!!')
            return None
        elif '无效的验证码' in responseHtml:
            l.warn('验证码有误!!')
            return None
        else:
            print(responseHtml)
            l.error('未知错误\n登录失败!!!!!')
            return None
