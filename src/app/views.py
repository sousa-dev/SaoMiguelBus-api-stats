import collections
from difflib import SequenceMatcher

import requests
from django.shortcuts import render
from django.utils import timezone
from django.db.models import QuerySet
from numpy import full
from rest_framework.decorators import api_view
from rest_framework.response import Response
from app.models import Stop, Route, Stat, ReturnRoute, LoadRoute, Variables, Ad, Group
from app.serializers import StopSerializer, RouteSerializer, StatSerializer, ReturnRouteSerializer, LoadRouteSerializer, VariablesSerializer, AdSerializer, GroupSerializer
from django.views.decorators.http import require_GET, require_POST
from datetime import datetime, date, timedelta
from statistics import median
import json

#Get All Stops
@api_view(['GET'])
@require_GET
def get_all_stops_v1(request):
    if request.method == 'GET':
        all_stops = Stop.objects.all()
        serializer = StopSerializer(all_stops, many=True)
        return Response(serializer.data)

#Get All Routes
@api_view(['GET'])
@require_GET
def get_all_routes_v1(request):
    if request.method == 'GET':
        all_routes = Route.objects.all()
        serializer = RouteSerializer(all_routes, many=True)
        return Response(serializer.data)

@api_view(['GET'])
@require_GET
def get_trip_v1(request):
    if request.method == 'GET':
        try:
            routes = Route.objects.all()
            routes = routes.exclude(disabled=True)
            origin = request.GET.get('origin', '')

            if origin in ['Povoacão', 'Lomba do Loucão', 'Ponta Garca']:
                origin = origin.replace('c', 'ç')
            routes = routes.filter(stops__icontains=origin) if origin != '' else routes

            destination = request.GET.get('destination', '')

            if destination in ['Povoacão', 'Lomba do Loucão', 'Ponta Garca']:
                destination = destination.replace('c', 'ç')

            if origin == '' or destination == '':
                return Response({'error': 'Origin and destination are required'})
            routes = routes.filter(stops__icontains=destination) if destination != '' else routes
            for route in routes:
                routes = routes.exclude(id=route.id) if str(route.stops).find(origin) > str(route.stops).find(destination) else routes
            type_of_day = request.GET.get('day', '')
            if type_of_day != '':
                routes = routes.filter(type_of_day=type_of_day.upper())
            start_time = request.GET.get('start', '')
            if start_time != '':
                for route in routes:
                    route_start_time = route.stops.split(',')[0].split(':')[1].replace('{','').replace('\'','').strip()
                    route_start_time_hour = int(route_start_time.split('h')[0])
                    route_start_time_minute = int(route_start_time.split('h')[1])
                    routes = routes.exclude(id=route.id) if route_start_time_hour < int(start_time.split('h')[0]) or (route_start_time_hour == int(start_time.split('h')[0]) and route_start_time_minute < int(start_time.split('h')[1])) else routes
            full = True if request.GET.get('full', '').lower() == 'true' else False
            if not full:
                #TODO: format route.stops to exclude stops outside the scope
                pass
            #TODO: get origin, destination, start and end time
            return_routes = [ReturnRoute(route.id, route.route, origin, destination, route.stops.split(':')[1].split(",")[0].replace('\'', '').strip(), route.stops.split(':')[-1].split(",")[0].replace('\'', '').replace('}', '').strip(), route.stops, route.type_of_day, route.information).__dict__ for route in routes]
            return Response(return_routes)
        except Exception as e:
            print(e)
            return Response(status=404)

@api_view(['GET'])
@require_GET
def get_route_v1(request, route_id):
    if request.method == 'GET':
        try:
            routes = Route.objects.all()
            routes = routes.filter(route__icontains=route_id)
            serializer = RouteSerializer(routes, many=True)
            #TODO: Return a new formatted entity
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(status=404)

@api_view(['GET'])
@require_GET
def get_stats_v1(request):
    if request.method == 'GET':
        try:
            stats = Stat.objects.all()
            serializer = StatSerializer(stats, many=True)
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(status=404)

@api_view(['POST'])
@require_POST
def add_stat_v1(request):
    if request.method == 'POST':
        try:
            stat = Stat()
            stat.request = request.GET.get('request', 'NA')
            stat.origin = request.GET.get('origin', '')
            stat.destination = request.GET.get('destination', '')
            stat.type_of_day = request.GET.get('day', 'NA')
            stat.time = request.GET.get('time', 'NA')
            stat.platform = request.GET.get('platform', 'NA')
            stat.language = request.GET.get('language', 'NA')
            #stat.timestamp = datetime.now()
            stat.save()
            return Response({'status': 'ok'})
        except Exception as e:
            print(e)
            return Response(status=404)
        
@api_view(['GET'])
@require_GET
def get_group_stats_v1(request):
    if request.method == "GET":
        try:
            groups = request.GET.get('group', '')
            if groups == '':
                return Response({'error': 'Group is required'})    
            start_time = request.GET.get('start_time', datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() - timedelta(days=7).total_seconds())
            end_time = request.GET.get('end_time', datetime.now().replace(hour=23, minute=59, second=59, microsecond=0).timestamp() - timedelta(days=1).total_seconds())
            start_time = str(start_time).split('.')[0]
            end_time = str(end_time).split('.')[0]
            erase = False
            if erase:
                print("Erasing Groups Database...")
                Group.objects.all().delete()
                all_groups = all_states = requests.get('https://api.saomiguelbus.com/api/v1/groups')
                for group in all_groups.json():
                    gr = Group()
                    gr.name = group['name'].lower()
                    gr.stops = ",".join(group['stops'])
                    gr.save()
                print("Done! Added updates groups")     
                print("Erasing Stats Database...")
                # clear database
                Stat.objects.all().delete()
                # get all states from external api
                all_states = requests.get('https://api.saomiguelbus.com/api/v1/stats', params={'start_time': start_time, 'end_time': end_time})
                # Populate DB with the stats
                print("Adding new stats to the database...")
                for state in all_states.json():
                    stat = Stat()
                    stat.request = state['request']
                    stat.origin = get_most_similar_stop(state['origin']) if state['origin'] != 'NA' else state['origin']
                    stat.destination = get_most_similar_stop(state['destination']) if state['destination'] != 'NA' else state['destination']
                    stat.type_of_day = state['type_of_day']
                    stat.time = state['time']
                    stat.platform = state['platform']
                    stat.language = state['language']
                    stat.timestamp = datetime.strptime(state['timestamp'], "%Y-%m-%dT%H:%M:%S.%fZ")
                    stat.save()
                print("Done! Added " + str(len(all_states.json())) + " stats to the database...")

            response = {}
            detailed_impressions = []            
            platform = request.GET.get('platform', 'all')
            language = request.GET.get('language', 'all')
    
            start_time = timezone.make_aware(datetime.fromtimestamp(int(start_time)), timezone.get_current_timezone())
            end_time = timezone.make_aware(datetime.fromtimestamp(int(end_time)), timezone.get_current_timezone())
            
            response['start_time'] = start_time
            response['end_time'] = end_time

            stats = Stat.objects.all()
            print("start")
            print(len(stats)) 
            print((start_time, end_time))
            stats = stats.filter(timestamp__range=(start_time, end_time))
            print("after time filter")
            print(len(stats)) 
            stats = stats.filter(language=language) if language != 'all' else stats
            if platform != 'all':
                if platform.find(',') != -1:
                    #remove stats that are not from the platform.split(',')
                    for stat in stats:
                        if stat.platform not in platform.split(','):
                            stats = stats.exclude(id=stat.id)
                else:
                    stats = stats.filter(platform=platform)

            print("before home page")
            print(len(stats)) 
            search_stops = []
            home_page_impressions = 0
            #home_page_detailed_impressions = []
            for group in groups.split(','):
                if group == "home":
                    # Get the median value of the home page impressions
                    daily_loads = [
                        len(stats.filter(request='android_load', timestamp__range=(start_time + timedelta(days=i), start_time + timedelta(days=i+1))))
                        for i in range((end_time - start_time).days)
                    ]
                    median_loads = median(daily_loads)                
                    home_page_impressions = int(median_loads * (end_time - start_time).days)                  
                    continue

                for stop in Group.objects.get(name=group).stops.split(','):
                        search_stops.append(stop)

            response['search_stops'] = search_stops

            # Find stats that have at least one of the stops at destination     
            # TODO: Fix this part     
            print("Before")
            print(len(stats))      
            # for stat in stats:
            #     if stat.destination == 'NA':
            #         stats = stats.exclude(id=stat.id)
            #         continue
            #     if stat.destination in search_stops or get_most_similar_stop(stat.destination) in search_stops:
            #         continue
            #     else:
            #         stats = stats.exclude(id=stat.id)
            new_stats = Stat.objects.none()
            for stop in search_stops:
                new_stats |= stats.filter(destination__icontains=stop)
            stats = new_stats
            print("after")
            print(len(stats))

            response['total_impressions'] = len(stats) + home_page_impressions
            response['home_page_impressions'] = home_page_impressions
            response['search_page_impressions'] = len(stats.filter(request='get_route'))
            response['find_page_impressions'] = len(stats.filter(request='find_routes'))
            response['directions_page_impressions'] = len(stats.filter(request='get_directions'))

            for stat in stats:
                detailed_impressions.append(get_detailed_impression(stat))
                    
            response['detailed_impressions'] = detailed_impressions + [f"{home_page_impressions} pessoas viram o anúncio ao entrar na app"]

            return Response(response)
        
        except Exception as e:
            print(e)
            return Response(status=404)

def get_detailed_impression(stat):
    impression = {}
    # Get a detailed impression from stat
    type_of_request = stat.request
    origin = stat.origin
    destination = stat.destination
    type_of_day = stat.type_of_day
    time = stat.time
    platform = stat.platform
    language = stat.language
    timestamp = stat.timestamp
    # only keep the values != 'NA'
    if type_of_request != 'NA':
        if type_of_request == "android_load":
            impression['type_of_request'] = "Abriu a Home Page"
        elif type_of_request == "get_route":
            impression['type_of_request'] = "Pesquisou uma Rota"
        elif type_of_request == "find_routes":
            impression['type_of_request'] = "Pesquisou uma Rota na página 'Find'"
        elif type_of_request == "get_directions":
            impression['type_of_request'] = "Pediu direções"
        else:
            impression['type_of_request'] = type_of_request
    
    if origin != 'NA':
        impression['origin'] = origin
    if destination != 'NA':
        impression['destination'] = destination
    if type_of_day != 'NA':
        if type_of_day == "WEEKDAY":
            impression['type_of_day'] = "Dia da Semana"
        elif type_of_day == "SATURDAY":
            impression['type_of_day'] = "Sábado"
        elif type_of_day == "SUNDAY":
            impression['type_of_day'] = "Domingo ou Feriado"
        else:
            impression['type_of_day'] = type_of_day
    if time != 'NA':
        impression['time'] = time
    if platform != 'NA':
        impression['platform'] = platform
    if language != 'NA':
        impression['language'] = language
    if timestamp != 'NA':
        impression['timestamp'] = timestamp.strftime('%d-%m-%Y %H:%M')
    return impression
    

@api_view(['GET'])
@require_GET
def get_ad_v1(request):
    ads = Ad.objects.all()
    if request.method == 'GET':
        ad_time = request.GET.get('now', timezone.now().timestamp())
        advertise_on = request.GET.get('on', 'all').lower()
        platform = request.GET.get('platform', 'all')
        datetime_ad_time = timezone.make_aware(datetime.fromtimestamp(float(ad_time)), timezone.get_default_timezone())
        ads = ads.filter(status='active')
        ads = ads.filter(platform=platform) if platform != 'all' else ads
        ads = ads.filter(start__lte=datetime_ad_time, end__gte=datetime_ad_time)

        # Verify if there is multiple ad campaigns for the same advertise_on
        verify = request.GET.get('verify', False)
        if verify:
            for ad in ads:
                groups = ad.advertise_on.split(',')
                for ad_ in ads:
                    if ad.id != ad_.id:
                        groups_ = ad_.advertise_on.split(',')
                        for group in groups:
                            if group in groups_:
                                return Response({'error': 'There are two active ads for the same campaign',
                                                 'ad-1': AdSerializer(ad).data,
                                                 'ad-2': AdSerializer(ad_).data})

        if advertise_on in ["home", "all"]:
            ads = ads.filter(advertise_on__icontains=advertise_on) if advertise_on != 'all' else ads
        else:
            stops = advertise_on.split('->') 
            origin = stops[0].strip()
            destination = stops[-1].strip()

            destination_ads = ads.filter(advertise_on__icontains=get_advertise_on_value(destination))
            #Priority for destination ads
            if destination_ads.count() > 0:
                ads = destination_ads
            else:
                ads = ads.filter(advertise_on__icontains=get_advertise_on_value(origin))
                
        # If multiple ads are found, choose a random one
        if ads.count() > 1:
            print('Multiple ads found for time: ' + str(ad_time))
            print('Choosing a random ad from the list:' )
            for ad in ads:
                print(ad)
            ads = ads.order_by('?')[:1]

        # Return a default ad if no ads are found
        if ads.count() == 0:
            ads = Ad.objects.filter(status='default')
            #Choose a random default ad
            ads = ads.order_by('?')[:1]

        if ads.count() == 0:
            print('No ads found for time: ' + str(ad_time))
            return Response(status=404)
        
        ad = ads[0]
        serializer = AdSerializer(ad)
        ad.seen += 1 
        ad.save()
        return Response(serializer.data)
    
#Get advertise on value based on the stop
def get_advertise_on_value(stop):
    #Find the group which the stop belongs to
    group = Group.objects.filter(stops__icontains=stop)
    if group.count() > 0:
        group = group[0]
        return group.name
    most_similar_stop = get_most_similar_stop(stop)
    group = Group.objects.filter(stops__icontains=most_similar_stop)
    if group.count() > 0:
        group = group[0]
        return group.name
    
    return "not found"

#Get the most similar stop
def get_most_similar_stop(stop):
    stops = Stop.objects.all()
    most_similar_stop = stop
    most_similar_stop_score = 0
    for stop_entity in stops:
        score = SequenceMatcher(
            lambda x: x in ['do', 'da', 'das', 'dos', 'de', ' '], 
            stop_entity.name.lower(), stop.lower()).ratio()
        if score > most_similar_stop_score:
            most_similar_stop = stop_entity.name
            most_similar_stop_score = score
    return most_similar_stop


#Increase ad clicked counter
@api_view(['POST'])
@require_POST
def click_ad_v1(request):
    if request.method == 'POST':
        try:
            ad_id = request.GET.get('id', '')
            if ad_id == '':
                return Response(status=404)
            ad = Ad.objects.get(id=ad_id)
            ad.clicked += 1
            ad.save()
            return Response({'status': 'ok'})
        except Exception as e:
            print(e)
            return Response(status=404)

@api_view(['GET'])
@require_GET
def get_all_groups_v1(request):
    if request.method == 'GET':
        if request.GET.get('verify', False):
            all_stops_obj = Stop.objects.all()
            all_stops_names = [stop.name for stop in all_stops_obj]
            all_groups = Group.objects.all()
            all_groups_stops = [group.stops for group in all_groups]
            all_groups_stops = [stop for stops in all_groups_stops for stop in stops.split(',')]
            # check for duplicates on all_groups_stops and if all_stops_names are in all_groups_stops
            if len(all_groups_stops) != len(set(all_groups_stops)) or not set(all_stops_names).issubset(set(all_groups_stops)):
                #Get missing stops
                missing_stops = set(all_stops_names) - set(all_groups_stops)
                #get duplicated stops
                duplicated_stops = [item for item, count in collections.Counter(all_groups_stops).items() if count > 1]

                return Response({'status': 'error', 'message': 'There is a problem with the defined groups', 
                                 'Missing stops': str(missing_stops), 
                                 'Duplicated stops':  str(duplicated_stops)})
        try:
            groups = Group.objects.all()
            serializer = GroupSerializer(groups, many=True)
            for group in serializer.data:
                group['name'] = group['name'].title()
                group['stops'] = group['stops'].split(',')
            return Response(serializer.data)
        except Exception as e:
            print(e)
            return Response(status=404)




@api_view(['GET'])
@require_GET
def get_android_load_v1(request):
        if request.method == 'GET':
            try:
                all_routes = Route.objects.all()
                all_routes = all_routes.exclude(disabled=True)
                routes = []
                for route in all_routes:
                    stops = route.stops.replace('\'', '').replace('{', '').replace('}', '').split(',')
                    all_stops = [stop.split(':')[0].strip() for stop in stops]
                    all_times = [stop.split(':')[1].strip() for stop in stops]
                    routes.append(LoadRoute(route.id, route.route, all_stops, all_times, route.type_of_day, route.information).__dict__)
                return Response(routes)
            except Exception as e:
                print(e)
                return Response(status=404)

@api_view(['GET'])
@require_GET
def get_android_load_v2(request):
        if request.method == 'GET':
            try:
                all_routes = Route.objects.all()
                all_routes = all_routes.exclude(disabled=True)
                routes = []
                try:
                    variable = Variables.objects.all().first().__dict__
                    routes = [{'version': variable['version'], 'maps': variable['maps']}]
                except Exception as e:
                    print(e)
                for route in all_routes:
                    stops = route.stops.replace('\'', '').replace('{', '').replace('}', '').split(',')
                    all_stops = [stop.split(':')[0].strip() for stop in stops]
                    all_times = [stop.split(':')[1].strip() for stop in stops]
                    routes.append(LoadRoute(route.id, route.route, all_stops, all_times, route.type_of_day, route.information).__dict__)
                return Response(routes)
            except Exception as e:
                print(e)
                return Response(status=404)

@api_view(['GET'])
@require_GET
def index (request):
    return render(request, 'app/templates/index.html')

@api_view(['GET'])
@require_GET
def stats (request):
    start_time = request.GET.get('start_time', datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    end_time = request.GET.get('end_time', datetime.now().timestamp())
    start_time = datetime.fromtimestamp(int(start_time))
    end_time = datetime.fromtimestamp(int(end_time))

    # format to     
    start_time = start_time.strftime('%Y-%m-%d %H:%M:%S')
    end_time = end_time.strftime('%Y-%m-%d %H:%M:%S')

    ALL = Stat.objects.all()

    latest_n = int(request.GET.get('latest', '10'))
    most_searched_n = int(request.GET.get('most_searched', '10'))

    android_loads, android_loads_labels, android_loads_no = get_android_loads()

    latests_activity = [stat for stat in ALL.order_by('-timestamp')[:latest_n]]

    android_loads_today = android_loads.filter(timestamp__range=(start_time, end_time)) # filter objects created today
    get_routes_today = Stat.objects.filter(request="get_route").filter(timestamp__range=(start_time, end_time)) # filter objects created today
    find_routes_today = Stat.objects.filter(request="find_routes").filter(timestamp__range=(start_time, end_time)) # filter objects created today
    get_directions_today = Stat.objects.filter(request="get_directions").filter(timestamp__range=(start_time, end_time)) # filter objects created today


    #TODO: Get stops names conversions to portuguese
    '''Get Most Searched Destinations'''
    most_searched_destinations_labels, most_searched_destinations_values = get_most_searched("destination", ALL.filter(request='get_route').exclude(destination='null') | ALL.filter(request='get_directions').exclude(destination='null') | ALL.filter(request='find_routes').exclude(destination='null'), most_searched_n)
    most_searched_origins_labels, most_searched_origins_values = get_most_searched("origin", ALL.filter(request='get_route').exclude(origin='null'), most_searched_n)
    most_searched_routes_labels, most_searched_routes_values = get_most_searched("route", ALL.filter(request='get_route').exclude(origin='null').exclude(destination='null'), most_searched_n)
    
    #TODO: get route android vs web

    android_loads_timestamp_keys, android_loads_timestamp_values = get_android_loads_timestamp(android_loads, start_time, end_time)

    context = {
        'labels': android_loads_labels, 'no': android_loads_no, 'label': 'Android App Loads (%)',
        'latests_activity': latests_activity, 
        'android_loads_timestamp_keys': android_loads_timestamp_keys, 'android_loads_timestamp_values': android_loads_timestamp_values,
        'android_loads_today_count': android_loads_today.count(), 'get_routes_today': get_routes_today.count(), 'find_routes_today': find_routes_today.count(), 'get_directions_today': get_directions_today.count(),
        'most_searched_destinations_labels': most_searched_destinations_labels, 'most_searched_destinations_values': most_searched_destinations_values,
        'most_searched_origins_labels': most_searched_origins_labels, 'most_searched_origins_values': most_searched_origins_values,
        'most_searched_routes_labels': most_searched_routes_labels, 'most_searched_routes_values': most_searched_routes_values,
        'start_time': start_time,
        'end_time': end_time,
        }
    
    return render(request, 'app/templates/statistics.html', context)

def get_android_loads_timestamp(android_loads, start_time, end_time):
    android_loads = android_loads.filter(timestamp__range=(start_time, end_time))
    android_loads_timestamp = {}
    for android_load in android_loads:
        hour = android_load.timestamp.strftime('%Y-%m-%d %H:00:00')
        if hour in android_loads_timestamp:
            android_loads_timestamp[hour] += 1
        else:
            android_loads_timestamp[hour] = 1
    return android_loads_timestamp.keys(), android_loads_timestamp.values()

def get_android_loads():
    android_loads = Stat.objects.filter(request='android_load')

    android_loads_en = int(android_loads.filter(language='en').count())*100/android_loads.count()
    android_loads_pt = int(android_loads.filter(language='pt').count())*100/android_loads.count()
    android_loads_esp = int(android_loads.filter(language='es').count())*100/android_loads.count()
    android_loads_fr = int(android_loads.filter(language='fr').count())*100/android_loads.count()
    android_loads_ger = int(android_loads.filter(language='de').count())*100/android_loads.count()
    android_loads_other = 100.0 - (android_loads_pt + android_loads_en + android_loads_fr + android_loads_ger + android_loads_esp)

    android_loads_labels = ['Portuguese', 'English', "Spanish", 'French', 'German', 'Other']
    android_loads_no = [android_loads_pt, android_loads_en,  android_loads_esp, android_loads_fr, android_loads_ger, android_loads_other]

    return android_loads, android_loads_labels, android_loads_no

def get_most_searched(n, stats, most_searched_n):
    most_searched = {}
    for stat in stats: 
        key = get_dict_key(n, stat)
        if key in most_searched:
            most_searched[key] += 1
        else:
            most_searched[key] = 1

    stops = [origin for origin in most_searched.keys()]

    most_searched_labels = sorted(stops, key=lambda x: most_searched[x], reverse=True)[:most_searched_n]
    most_searched_values = [most_searched[destination] for destination in most_searched_labels]

    return most_searched_labels, most_searched_values

def get_dict_key(n, stat):
    if n == 'destination':
        return stat.destination
    elif n == 'origin':
        return stat.origin
    elif n == 'route':
        return f"{stat.origin} -> {stat.destination}"



