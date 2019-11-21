#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import os
from logging import debug, info, warning, error, exception
import traceback
# from time import sleep
from datetime import datetime, timedelta

from io import StringIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header
from email.generator import Generator
import smtplib

from time import mktime
from html.parser import HTMLParser


from tornado.web import (Application, RedirectHandler, RequestHandler,
                         StaticFileHandler, HTTPError)
from tornado.ioloop import IOLoop
from tornado.options import (
    parse_config_file, parse_command_line, define, options)
from tornado import autoreload, gen
from tornado.httpclient import AsyncHTTPClient

import feedparser


define('debug', default=False, help='debug mode')
define('port', default=9008, help='port to run on', type=int)
define('site_url', default='https://www.wwpass.com/', help='Site URL')
define('cookie_secret', help='secret key for encode cookie')
define('email', default="ivladimirskiy@ya.ru", help='email for mails')
define('counters', default=False, help='add counters on the pages', type=bool)


def date_hook(json_dict):
    for (key, value) in json_dict.items():
        try:
            json_dict[key] = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        except:
            pass
    return json_dict


def send_email(sender, recipient, subject, text, server='localhost'):
    # Open the plain text file whose name is in textfile for reading.
    # msg = EmailMessage()
    # msg.set_content(text)
    #
    # # me == the sender's email address
    # # you == the recipient's email address
    # msg['Subject'] = subject
    # msg['Subject'] = subject
    # msg['From'] = sender
    #
    # # Send the message via our own SMTP server.
    # s = smtplib.SMTP(server)
    # s.send_message(msg)
    # s.quit()

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "%s" % Header(subject, 'utf-8')
    # Only descriptive part of recipient and sender shall be encoded, not the email address
    # msg['From'] = "\"%s\" <%s>" % (Header(from_address[0], 'utf-8'), from_address[1])
    # msg['To'] = "\"%s\" <%s>" % (Header(recipient[0], 'utf-8'), recipient[1])
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient

    # Attach both parts
    # htmlpart = MIMEText(html, 'html', 'UTF-8')
    textpart = MIMEText(text, 'plain', 'UTF-8')
    # msg.attach(htmlpart)
    msg.attach(textpart)

    # Create a generator and flatten message object to 'file’
    str_io = StringIO()
    g = Generator(str_io, False)
    g.flatten(msg)
    # str_io.getvalue() contains ready to sent message

    # Optionally - send it – using python's smtplib
    # or just use Django's
    s = smtplib.SMTP(server)
    # s.ehlo()
    # s.starttls()
    # s.ehlo()
    # s.login("", "")
    s.sendmail(sender, recipient, str_io.getvalue())

def send_bcc_email(sender, recipient, bcc, subject, text, server='localhost'):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = recipient
    msg['BCC'] = bcc

    textpart = MIMEText(text, 'plain', 'UTF-8')
    msg.attach(textpart)

    str_io = StringIO()
    g = Generator(str_io, False)
    g.flatten(msg)
    s = smtplib.SMTP(server)
    s.sendmail(sender, [recipient, bcc], str_io.getvalue())


SUBMIT_TMP = ('demo', 'ebook')
BLOG_RSS_FEED_URL = 'https://www.wwpass.com/blog/blog.rss'
blog_feed = {
    'last_update': None,
    'items': [],
    'posts': []
}


class MixinCustomHandler():

    def write_error(self, status_code, **kwargs):
        # pylint: disable=E1101
        info('%d <- :: write_error' % status_code)
        try:
            if self.settings.get("serve_traceback") and "exc_info" in kwargs:
                # in debug mode, try to send a traceback
                self.set_header('Content-Type', 'text/plain')
                for line in traceback.format_exception(*kwargs["exc_info"]):
                    self.write(line)
                self.finish()
            else:
                self.render('error.html', status_code=status_code, reason=self._reason)
        except Exception as err:  # pylint: disable=W0703
            exception(err)
            self.set_header('Content-Type', 'text/plain')
            self.write('500: EPIC SERVER FAIL. PLEASE, TRY AGAIN LATER')
            self.finish()

    def location_has_seo_stop_words(self):
        filters = ['utm_content', 'from', 'p', '__hstc']
        
        for it in filters:
            if self.get_argument(it, False):
                return True

        return False

    def render(self, template_name, alternative=False, **kwargs):
        has_super_cookie = self.get_cookie('cdc_id') or None
        RequestHandler.render(self,
            template_name,
            alternative=alternative,
            site_url=options.site_url,
            counters=options.counters,
            has_super_cookie=has_super_cookie,
            manage_domain='manage.wwpass.com',
            location_has_seo_stop_words=self.location_has_seo_stop_words,
            **kwargs)

        # if self.settings.get("serve_traceback") and "exc_info" in kwargs:
        #     # in debug mode, try to send a traceback
        #     self.set_header('Content-Type', 'text/plain')
        #     for line in traceback.format_exception(*kwargs["exc_info"]):
        #         self.write(line)
        #     self.finish()
        # else:
        #     self.finish("<html><title>%(code)d: %(message)s</title>"
        #                 "<body>%(code)d: %(message)s</body></html>" % {
        #                     "code": status_code,
        #                     "message": self._reason,
        #                 })


class BaseHandler(MixinCustomHandler, RequestHandler):
    render = MixinCustomHandler.render


class CustomStatic(MixinCustomHandler, StaticFileHandler):
    render = MixinCustomHandler.render


class SubmitFormHandler(BaseHandler):

    def get(self):
        self.redirect('/')

    def post(self):
        form_name = self.get_argument('name', None)
        form_email = self.get_argument('email', None)
        form_phone = self.get_argument('phone', None)
        form_browser_date = self.get_argument('browserDate', None)
        form_url = self.get_argument('url', None)

        try:
            info(repr(form_name))
            info(repr(form_email))
            info(repr(form_phone))

            message_text = self.render_string(
                'mails/talk.txt',
                name=form_name,
                email=form_email,
                phone=form_phone,

                browser_date=form_browser_date,
                url=form_url
            )

            subject = 'Request from site: %s UTC' % datetime.utcnow()

            # if form_url:
                
            send_email('noreply@wwpass.com', form_email, subject, message_text)
            send_email('noreply@wwpass.com', options.email, subject, message_text)
            info('send_mail: %s' % form_email)
            
        except Exception as e:
            exception(e)
            error(repr(form_name))
            error(repr(form_email))
            error(repr(form_phone))

        # self.write('post::submitForm')
        # self.finish()

        # template = 'submit-%s.html' % form_type if form_type in SUBMIT_TMP else 'submit.html'

        # self.render(template)
        self.write('done')

"""
# MailChimp Add User
# add John Doe with email john.doe@example.com to list matching id '123456'

client.lists.members.create('123456', {
    'email_address': 'john.doe@example.com',
    'status': 'subscribed',
    'merge_fields': {
        'FNAME': 'John',
        'LNAME': 'Doe',
    },
})
"""

class OGParser(HTMLParser):
    og = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'meta':
            try:
                matches = next(x for x in attrs if x[0] == 'property')
                name_og = matches[1]
                if name_og.startswith('og:'):
                    matches = next(x for x in attrs if x[0] == 'content')
                    self.og[name_og[3:]] = matches[1]
            except StopIteration as e:
                pass
    
    def get_og(self):
        return self.og


class HomePage(BaseHandler):
    @gen.coroutine
    def get(self):
        if not blog_feed['items'] or \
            not blog_feed['last_update'] or \
            datetime.utcnow() > blog_feed['last_update'] + timedelta(hours=2):

            info('Fetch Blog Feed')
            raw_blog_feed = feedparser.parse(BLOG_RSS_FEED_URL)

            # debug(raw_blog_feed['entries'][0].keys())
            # debug(json.dumps((raw_blog_feed['entries'][0]), indent=2))

            blog_feed['last_update'] = datetime.utcnow()
            blog_feed['items'] = raw_blog_feed['entries']
            blog_feed['posts'] = []
            last_blog = blog_feed['items'][:3]
            for item in last_blog:
                http_client = AsyncHTTPClient()
                response = yield http_client.fetch(item['link'])
                http_client.close()

                p = OGParser()
                p.feed(response.body.decode('utf-8'))
                og = p.get_og()

                blog_feed['posts'].append({
                    'link': item['link'],
                    'title': item['title'],
                    'published_parsed': item['published_parsed'],
                    'author': item['author_detail']['name'],
                    'image': og['image'],
                    'description': og['description']
                })
        
        blog_feed_last_items = blog_feed['posts']
        # articles_last_items = articles[:3]
        # for item in blog_feed_last_items:
        #     debug(item['link'])
        #     self.write(item['title'] + '\n')
        # self.finish()

        self.render('main-landing.html',
            alternative=True,
            blog_feed=blog_feed_last_items,
            # articles=articles_last_items,
            datetime=datetime,
            mktime=mktime
            )


class TestHandler(BaseHandler):

    def get(self):
        raise HTTPError(500)


# class Newsroom(BaseHandler):

#     def get(self):
#         self.render('newsroom.html', articles=articles)


class TemplatePage(BaseHandler):

    def initialize(self, template, alternative=False):
        self.template = template
        self.alternative = alternative

    def get(self):
        self.render(self.template, alternative=self.alternative)


class ProxyAPI(RequestHandler):

    @gen.coroutine
    def get(self):
        # /api/version.txt?type=soft&platform=osx.10.11&package=pack

        # self.write(repr(self.request.uri))

        # atype = self.get_argument('type', None)
        # aplatform = self.get_argument('platform', None)
        # apackage = self.get_argument('package', None)

        url = 'https://a2.wwpass.com%s' % self.request.uri
        http_client = AsyncHTTPClient()
        response = yield http_client.fetch(url)

        # TODO: add correct status_code
        self.write(response.body)  # response

        debug(url)
        debug(response.code)
        debug(repr(response.body))

        # raise HTTPError(404)


base_path = os.path.abspath(os.path.dirname(__file__))
static_path = os.path.realpath(os.path.join(base_path, '../static'))
template_path = os.path.realpath(os.path.join(base_path, 'templates'))


class App(Application):

    def __init__(self):

        handlers = [
            ('/submit', SubmitFormHandler),
            # ('/submit/', SubmitFormHandler),


            ('/', HomePage),

            ('/file', TemplatePage, {
              'template': 'tickets.pdf'
            }),


            ('/error', TestHandler),


            # ('/google9662725d6bb89c83.html', TemplatePage, {
            #     'template': 'google9662725d6bb89c83.html'
            # }),

            (r'/(.*)', CustomStatic, {'path': static_path})
        ]


        settings = dict(
            debug=options.debug,
            autoreload=True,
            xsrf_cookies=True,
            cookie_secret=options.cookie_secret,

            # static_path=static_path,
            template_path=template_path,
            default_handler_class=BaseHandler,
            # mc=mc_client
        )

        Application.__init__(self, handlers, **settings)


def main():
    # Loading application settings
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        parse_config_file(sys.argv[1])
        parse_command_line(sys.argv[1:])  # hack with config
    else:
        warning('Running without config: terminate')
        print('Example usage:')
        print('  python main.py /path/to/production.conf [params]')
        exit()

    app = App()
    app.listen(options.port)

    info('Counters %s' % options.counters)
    info('Port %s' % options.port)

    autoreload.start()
    IOLoop.instance().start()

if __name__ == '__main__':
    main()
