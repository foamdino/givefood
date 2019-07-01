from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.contrib.staticfiles.views import serve

import givefood.views

import session_csrf
session_csrf.monkeypatch()

from django.contrib import admin
admin.autodiscover()

urlpatterns = (
    url(r'^_ah/', include('djangae.urls')),

    # PUBLIC
    url(r'^$', givefood.views.public_index, name="public_index"),

    # ADMIN
    url(r'^admin/$', givefood.views.admin_index, name="admin_index"),

    url(r'^admin/order/new/$', givefood.views.admin_order_form, name="admin_neworder"),
    url(r'^admin/order/(?P<id>[-\w]+)/$', givefood.views.admin_order_form, name="admin_order"),

    url(r'^admin/foodbank/new/$', givefood.views.admin_foodbank_form, name="admin_newfoodbank"),
    url(r'^admin/foodbank/(?P<slug>[-\w]+)/$', givefood.views.admin_foodbank_form, name="admin_foodbank"),



    url(r'^csp/', include('cspreports.urls')),
    url(r'^auth/', include('djangae.contrib.gauth.urls')),
)

if settings.DEBUG:
    urlpatterns += tuple(static(settings.STATIC_URL, view=serve, show_indexes=True))
