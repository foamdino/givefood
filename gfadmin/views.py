import csv
import logging
from datetime import datetime, timedelta

from djangae.environment import is_production_environment

from google.appengine.api import urlfetch, memcache
from google.appengine.ext import deferred

from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, HttpResponseForbidden
from django.core.urlresolvers import reverse
from django.template import RequestContext
from django.template.loader import render_to_string
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from django.utils.encoding import smart_str

from givefood.const.general import PACKAGING_WEIGHT_PC
from givefood.func import get_all_foodbanks, get_all_locations, get_cred, post_to_facebook, post_to_twitter, post_to_subscriber, send_email
from givefood.models import Foodbank, Order, OrderLine, OrderItem, FoodbankChange, FoodbankLocation, ApiFoodbankSearch, ParliamentaryConstituency, GfCredential, FoodbankSubscriber
from givefood.forms import FoodbankForm, OrderForm, NeedForm, FoodbankPoliticsForm, FoodbankLocationForm, FoodbankLocationPoliticsForm, ParliamentaryConstituencyForm, OrderItemForm, GfCredentialForm


def index(request):

    foodbanks = Foodbank.objects.all().order_by("-last_order")[:20]

    today = datetime.today()
    today_orders = Order.objects.filter(delivery_date = today).order_by("delivery_hour")

    upcoming_orders = Order.objects.filter(delivery_date__gt = today).order_by("delivery_date")

    prev_order_threshold = datetime.now() - timedelta(days=1)
    prev_orders = Order.objects.filter(delivery_datetime__lt = prev_order_threshold).order_by("-delivery_datetime")[:20]

    unpublished_needs = FoodbankChange.objects.filter(published = False).order_by("-created")
    published_needs = FoodbankChange.objects.filter(published = True).order_by("-created")[:20]

    template_vars = {
        "foodbanks":foodbanks,
        "today_orders":today_orders,
        "upcoming_orders":upcoming_orders,
        "prev_orders":prev_orders,
        "unpublished_needs":unpublished_needs,
        "published_needs":published_needs,
        "section":"home",
    }
    return render(request, "admin_index.html", template_vars)


def searches(request):

    searches = ApiFoodbankSearch.objects.all().order_by("-created")[:1000]

    template_vars = {
        "searches":searches,
        "section":"searches",
    }

    return render(request, "searches.html", template_vars)


def searches_csv(request):

    searches = ApiFoodbankSearch.objects.all().order_by("-created")[:20000]

    output = []
    response = HttpResponse (content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['created', 'query_type', 'query', 'nearest_foodbank', 'latt', 'long'])
    for search in searches:
        output.append([search.created, search.query_type, search.query, search.nearest_foodbank, search.latt(), search.long()])
    writer.writerows(output)
    return response


def search(request):

    query = request.GET.get("q")
    foodbank = get_object_or_404(Foodbank, name=query)

    return redirect("admin_foodbank", slug = foodbank.slug)


def foodbanks(request):

    sort_options = [
        "name",
        "last_order",
        "last_need",
        "created",
    ]
    sort = request.GET.get("sort", "name")
    if sort not in sort_options:
        return HttpResponseForbidden()

    sort_string = sort
    if sort != "name":
        sort = "-%s" % (sort)

    foodbanks = Foodbank.objects.all().order_by(sort)

    template_vars = {
        "sort":sort_string,
        "foodbanks":foodbanks,
        "section":"foodbanks",
    }
    return render(request, "foodbanks.html", template_vars)


def foodbanks_csv(request):

    foodbanks = Foodbank.objects.all().order_by("-created")

    output = []
    response = HttpResponse (content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['name', 'postcode', 'charity_number', 'country', 'last_order', 'last_need', 'no_locations', 'network', 'closed', 'url', 'created', 'modified'])
    for foodbank in foodbanks:
        output.append([foodbank.name, foodbank.postcode, foodbank.charity_number, foodbank.country, foodbank.last_order, foodbank.last_need, foodbank.no_locations, foodbank.network, foodbank.is_closed, foodbank.url, foodbank.created, foodbank.modified])
    writer.writerows(output)
    return response


def foodbanks_christmascards(request):

    foodbanks = Foodbank.objects.filter(is_closed = False).order_by("name")

    template_vars = {
        "foodbanks":foodbanks,
    }
    return render(request, "foodbanks_christmascards.html", template_vars)


def orders(request):

    sort_options = [
        "delivery_datetime",
        "created",
        "no_items",
        "weight",
        "calories",
        "cost",
    ]
    sort = request.GET.get("sort", "delivery_datetime")
    if sort not in sort_options:
        return HttpResponseForbidden()

    sort_string = sort
    sort = "-%s" % (sort)

    orders = Order.objects.all().order_by(sort)

    template_vars = {
        "sort":sort_string,
        "orders":orders,
        "section":"orders",
    }
    return render(request, "orders.html", template_vars)


def orders_csv(request):

    orders = Order.objects.all().order_by("-created")

    output = []
    response = HttpResponse (content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['id', 'created', 'delivery', 'delivery_provider', 'foodbank', 'country', 'weight', 'calories', 'items', 'cost'])
    for order in orders:
        output.append([order.order_id, order.created, order.delivery_datetime, order.delivery_provider, order.foodbank_name, order.country, order.weight, order.calories, order.no_items, order.cost])
    writer.writerows(output)
    return response


def needs(request):

    needs = FoodbankChange.objects.all().order_by("-created")[:1000]

    template_vars = {
        "needs":needs,
        "section":"needs",
    }
    return render(request, "needs.html", template_vars)


def needs_csv(request):

    needs = FoodbankChange.objects.all().order_by("-created")

    output = []
    response = HttpResponse (content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['id', 'created', 'foodbank', 'needs', 'input_method'])
    for need in needs:
        output.append([need.need_id, need.created, need.foodbank_name, smart_str(need.change_text), need.input_method()])
    writer.writerows(output)
    return response


def order(request, id):

    order = get_object_or_404(Order, order_id = id)

    template_vars = {
        "order":order,
    }
    return render(request, "order.html", template_vars)


def order_form(request, id = None):

    foodbank = None
    page_title = None
    foodbank_slug = request.GET.get("foodbank")
    if foodbank_slug:
        foodbank = Foodbank.objects.get(slug=foodbank_slug)

    if id:
        order = get_object_or_404(Order, order_id = id)
    else:
        order = None

    if request.POST:
        form = OrderForm(request.POST, instance=order)
        if form.is_valid():
            order = form.save()
            return redirect("admin_order", id = order.order_id)
    else:
        if foodbank:
            form = OrderForm(instance=order, initial={"foodbank":foodbank})
        else:
            form = OrderForm(instance=order)

    if id:
        page_title = "Edit %s" % str(order.order_id)
    else:
        if foodbank:
            page_title = "New Order for %s" % foodbank
        else:
            page_title = "New Order"

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


@require_POST
def order_send_notification(request, id = None):

    order = get_object_or_404(Order, order_id = id)
    email_body = render_to_string("notification_email.txt",{"order":order})
    send_email(
        to = order.foodbank.notification_email,
        cc = "deliveries@givefood.org.uk",
        subject = "Food donation from Give Food (%s)" % (order.order_id),
        body = email_body,
    )

    order.notification_email_sent = datetime.now()
    order.save()
    redir_url = "%s?donenotification=true" % (reverse("admin_order", kwargs={'id': order.order_id}))
    return redirect(redir_url)


def order_delete(request, id):

    order = get_object_or_404(Order, order_id = id)
    order.delete()
    return redirect(reverse("admin_index"))


def foodbank(request, slug):

    foodbank = get_object_or_404(Foodbank, slug = slug)

    template_vars = {
        "foodbank":foodbank,
    }
    return render(request, "foodbank.html", template_vars)


def foodbank_form(request, slug = None):

    if slug:
        foodbank = get_object_or_404(Foodbank, slug = slug)
        page_title = "Edit %s Food Bank" % (foodbank.name)
    else:
        foodbank = None
        page_title = "New Food Bank"

    if request.POST:
        form = FoodbankForm(request.POST, instance=foodbank)
        if form.is_valid():
            foodbank = form.save()
            return redirect("admin_foodbank", slug = foodbank.slug)
    else:
        form = FoodbankForm(instance=foodbank)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def foodbank_politics_form(request, slug = None):

    if slug:
        foodbank = get_object_or_404(Foodbank, slug = slug)
        page_title = "Edit %s Food Bank Politics" % (foodbank.name)
    else:
        foodbank = None

    if request.POST:
        form = FoodbankPoliticsForm(request.POST, instance=foodbank)
        if form.is_valid():
            foodbank = form.save()
            return redirect("admin_foodbank", slug = foodbank.slug)
    else:
        form = FoodbankPoliticsForm(instance=foodbank)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def fblocation_form(request, slug = None, loc_slug = None):

    if slug:
        foodbank = get_object_or_404(Foodbank, slug = slug)
        page_title = "Edit %s Food Bank Location" % (foodbank.name)
    else:
        foodbank = None

    if loc_slug:
        foodbank_location = get_object_or_404(FoodbankLocation, foodbank = foodbank, slug = loc_slug)
    else:
        foodbank_location = None

    if request.POST:
        form = FoodbankLocationForm(request.POST, instance=foodbank_location)
        if form.is_valid():
            foodbank_location = form.save()
            return redirect("admin_foodbank", slug = foodbank_location.foodbank_slug)
    else:
        form = FoodbankLocationForm(instance=foodbank_location, initial={"foodbank":foodbank})

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def fblocation_politics_edit(request, slug, loc_slug):

    if slug:
        foodbank_location = get_object_or_404(FoodbankLocation, foodbank_slug = slug, slug = loc_slug)
        page_title = "Edit %s Food Bank Location Politics" % (FoodbankLocation.foodbank.name)
    else:
        foodbank_location = None

    if request.POST:
        form = FoodbankLocationPoliticsForm(request.POST, instance=foodbank_location)
        if form.is_valid():
            foodbank_location = form.save()
            return redirect("admin_foodbank", slug = foodbank_location.foodbank.slug)
    else:
        form = FoodbankLocationPoliticsForm(instance=foodbank_location)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


@require_POST
def fblocation_delete(request, slug, loc_slug):

    foodbank_location = get_object_or_404(FoodbankLocation, foodbank_slug = slug, slug = loc_slug)
    foodbank_location.delete()

    return redirect("admin_foodbank", slug = foodbank_location.foodbank_slug)


def need(request, id):

    need = get_object_or_404(FoodbankChange, need_id = id)
    subscribers = FoodbankSubscriber.objects.filter(foodbank = need.foodbank)
    
    template_vars = {
        "need":need,
        "subscribers":subscribers,
    }
    return render(request, "need.html", template_vars)


def need_form(request, id = None):

    if id:
        need = get_object_or_404(FoodbankChange, need_id = id)
        page_title = "Edit Need"
    else:
        need = None
        page_title = "New Need"

    foodbank = None
    foodbank_slug = request.GET.get("foodbank")
    if foodbank_slug:
        foodbank = Foodbank.objects.get(slug=foodbank_slug)

    if request.POST:
        form = NeedForm(request.POST, instance=need)
        if form.is_valid():
            need = form.save()
            return redirect("admin_need", id = need.need_id)
    else:
        if foodbank:
            form = NeedForm(instance=need, initial={"foodbank":foodbank})
        else:
            form = NeedForm(instance=need)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


@require_POST
def need_delete(request, id):

    need = get_object_or_404(FoodbankChange, need_id = id)
    deferred.defer(need.delete)
    return redirect("admin_index")


@require_POST
def need_publish(request, id, action):

    need = get_object_or_404(FoodbankChange, need_id = id)
    if action == "publish":
        need.published = True
    if action == "unpublish":
        need.published = False
    need.save()
    return redirect("admin_index")


@require_POST
def need_notifications(request, id):

    need = get_object_or_404(FoodbankChange, need_id = id)

    # Defer the postings
    deferred.defer(post_to_facebook, need, _queue="socialpost")
    deferred.defer(post_to_twitter, need, _queue="socialpost")

    # Update tweet time
    need.tweet_sent = datetime.now()
    need.save()

    # Email subscriptions
    subscribers = FoodbankSubscriber.objects.filter(foodbank = need.foodbank, confirmed = True)
    for subscriber in subscribers:
        deferred.defer(post_to_subscriber, need, subscriber)

    return redirect("admin_index")


def locations(request):

    sort_options = [
        "foodbank_name",
        "name",
        "parliamentary_constituency",
    ]
    sort = request.GET.get("sort", "foodbank_name")
    if sort not in sort_options:
        return HttpResponseForbidden()

    locations = FoodbankLocation.objects.all().order_by(sort)

    template_vars = {
        "sort":sort,
        "locations":locations,
        "section":"locations",
    }
    return render(request, "locations.html", template_vars)


def locations_loader_sa(request):

    sa_foodbank = Foodbank.objects.get(slug="salvation-army")

    with open('./givefood/data/sa_locations.csv') as csvfile:
        readCSV = csv.reader(csvfile, delimiter=',')
        for row in readCSV:

            logging.info(row)
            name = row[0]
            address = row[1]
            postcode = row[2]
            email = row[3]
            phone = row[4]
            lat_lng = row[5]

            try:
                foodbank_location = FoodbankLocation.objects.get(name=name,foodbank=sa_foodbank)
            except FoodbankLocation.DoesNotExist:
                foodbank_location = FoodbankLocation(
                    foodbank = sa_foodbank,
                    name = name,
                    address = address,
                    postcode = postcode,
                    email = email,
                    phone_number = phone,
                    latt_long = lat_lng,
                )
                foodbank_location.save()


    return HttpResponse("OK")


def items(request):

    items = OrderItem.objects.all()

    template_vars = {
        "items":items,
        "section":"items",
    }
    return render(request, "items.html", template_vars)


def item_form(request, slug = None):

    if slug:
        item = get_object_or_404(OrderItem, slug = slug)
        page_title = "Edit Item"
    else:
        item = None
        page_title = "New Item"

    if request.POST:
        form = OrderItemForm(request.POST, instance=item)
        if form.is_valid():
            need = form.save()
            return redirect("admin_items")
    else:
        form = OrderItemForm(instance=item)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def politics(request):

    foodbanks = get_all_foodbanks()
    locations = FoodbankLocation.objects.all()
    parlcons = ParliamentaryConstituency.objects.all().order_by("name")

    template_vars = {
        "foodbanks":foodbanks,
        "locations":locations,
        "parlcons":parlcons,
        "section":"politics",
    }
    return render(request, "politics.html", template_vars)


def politics_csv(request):

    foodbanks = get_all_foodbanks()
    locations = FoodbankLocation.objects.all()

    output = []
    response = HttpResponse (content_type='text/csv')
    writer = csv.writer(response)
    writer.writerow(['constituency', 'mp', 'mp_party', 'mp_parl_id'])
    for foodbank in foodbanks:
        output.append([foodbank.parliamentary_constituency, foodbank.mp, foodbank.mp_party, foodbank.mp_parl_id])
    for location in locations:
        output.append([location.parliamentary_constituency, location.mp, location.mp_party, location.mp_parl_id])
    writer.writerows(output)
    return response


def map(request):

    filter = request.GET.get("filter", "all")

    all_foodbanks = get_all_foodbanks()

    if filter == "all":
        foodbanks = all_foodbanks
    elif filter == "active":
        foodbanks = set()
        all_orders = Order.objects.all()
        for order in all_orders:
            foodbanks.add(order.foodbank)
    else:
        foodbank = get_object_or_404(Foodbank, slug=filter)
        foodbanks = []
        foodbanks.append(foodbank)
        for location in foodbank.locations():
            foodbanks.append(location)

    template_vars = {
        "foodbanks":foodbanks,
        "all_foodbanks":all_foodbanks,
        "filter":filter,
        "section":"map",
    }
    return render(request, "map.html", template_vars)


def stats(request):

    all_foodbanks = get_all_foodbanks()
    total_foodbanks = len(all_foodbanks)
    active_foodbanks = set()

    needs = FoodbankChange.objects.all()
    total_needs = len(needs)
    total_need_items = 0
    for need in needs:
        total_need_items = total_need_items + need.no_items()

    locations = get_all_locations()
    total_locations = len(locations) + total_foodbanks

    total_weight = 0
    total_calories = 0
    total_items = 0
    total_cost = 0

    all_orders = Order.objects.all()
    total_orders = len(all_orders)
    for order in all_orders:
        total_weight = total_weight + order.weight
        total_calories = total_calories + order.calories
        total_items = total_items + order.no_items
        total_cost = total_cost + order.cost
        active_foodbanks.add(order.foodbank_name)

    total_weight = total_weight / 1000
    total_weight_pkg = total_weight * PACKAGING_WEIGHT_PC
    total_cost = float(total_cost) / 100

    total_active_foodbanks = len(active_foodbanks)

    subscriptions = FoodbankSubscriber.objects.filter(confirmed = True)
    total_subscriptions = len(subscriptions)

    template_vars = {
        "total_foodbanks":total_foodbanks,
        "total_active_foodbanks":total_active_foodbanks,
        "total_weight":total_weight,
        "total_calories":total_calories,
        "total_items":total_items,
        "total_orders":total_orders,
        "total_cost":total_cost,
        "total_needs":total_needs,
        "total_need_items":total_need_items,
        "total_weight_pkg":total_weight_pkg,
        "total_locations":total_locations,
        "total_subscriptions":total_subscriptions,
        "section":"stats",
    }
    return render(request, "stats.html", template_vars)


def test_order_email(request, id):

    order = get_object_or_404(Order, order_id = id)

    template_vars = {
        "order":order,
    }
    return render(request, "notification_email.txt", template_vars, content_type='text/plain')


def resave_orders(request):

    orders = Order.objects.all().order_by("created")
    for order in orders:
        order.save()

    return HttpResponse("OK")


def parlcon_form(request, slug = None):

    if slug:
        parlcon = get_object_or_404(ParliamentaryConstituency, slug = slug)
        page_title = "Edit Parlimentary Constituency"
    else:
        parlcon = None
        page_title = "New Parlimentary Constituency"

    if request.POST:
        form = ParliamentaryConstituencyForm(request.POST, instance=parlcon)
        if form.is_valid():
            foodbank = form.save()
            return redirect("admin_politics")
    else:
        form = ParliamentaryConstituencyForm(instance=parlcon)

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def parlcon_loader(request):

    foodbanks = get_all_foodbanks()
    locations = get_all_locations()

    for foodbank in foodbanks:
        try:
            logging.info("trying fb parlcon %s" % foodbank.parliamentary_constituency_slug)
            parlcon = ParliamentaryConstituency.objects.get(slug = foodbank.parliamentary_constituency_slug)
        except ParliamentaryConstituency.DoesNotExist:
            logging.info("adding %s" % foodbank.parliamentary_constituency_slug)
            newparlcon = ParliamentaryConstituency(
                name = foodbank.parliamentary_constituency,
                mp = foodbank.mp,
                mp_party = foodbank.mp_party,
                mp_parl_id = foodbank.mp_parl_id,
            )
            newparlcon.save()


    for location in locations:
        try:
            logging.info("trying loc parlcon %s" % location.parliamentary_constituency_slug)
            parlcon = ParliamentaryConstituency.objects.get(slug = location.parliamentary_constituency_slug)
        except ParliamentaryConstituency.DoesNotExist:
            logging.info("adding %s" % location.parliamentary_constituency_slug)
            newparlcon = ParliamentaryConstituency(
                name = location.parliamentary_constituency,
                mp = location.mp,
                mp_party = location.mp_party,
                mp_parl_id = location.mp_parl_id,
            )
            newparlcon.save()

    return HttpResponse("OK")


def parlcon_loader_geojson(request):

    parlcons = ParliamentaryConstituency.objects.all()

    geojson_file = open('./givefood/data/parlcon.geojson', 'r')
    lines = geojson_file.readlines()

    for line in lines:
        # logging.info(line)
        for parlcon in parlcons:
            if not parlcon.boundary_geojson:
                if parlcon.name in line:
                    logging.info("Found " + parlcon.name)
                    parlcon.boundary_geojson = line
                    parlcon.save()

    return HttpResponse("OK")


def settings(request):

    template_vars = {
        "section":"settings",
    }
    return render(request, "settings.html", template_vars)


def credentials(request):

    credentials = GfCredential.objects.all().order_by("-created")

    template_vars = {
        "section":"settings",
        "credentials":credentials,
    }
    return render(request, "credentials.html", template_vars)

def credentials_form(request):

    if request.POST:
        form = GfCredentialForm(request.POST)
        if form.is_valid():
            need = form.save()
            return redirect("admin_credentials")
    else:
        form = GfCredentialForm()
        page_title = "New Credential"

    template_vars = {
        "form":form,
        "page_title":page_title,
    }
    return render(request, "form.html", template_vars)


def subscriptions(request):

    subscriptions = FoodbankSubscriber.objects.all().order_by("-created")

    template_vars = {
        "section":"settings",
        "subscriptions":subscriptions,
    }
    return render(request, "subscriptions.html", template_vars)


@require_POST
def delete_subscription(request):

    email = request.POST.get("email")
    subscriber = get_object_or_404(FoodbankSubscriber, email = email)
    subscriber.delete()

    return redirect("admin_subscriptions")


def clearcache(request):

    memcache.flush_all()
    return redirect("admin_index")