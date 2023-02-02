from app.models import Media, Season
from app.utils import helpers
from django.core.files import File
from django.db.models import Avg, Sum, Min, Max
import datetime


def add_media(request):
    metadata = request.session.get("metadata")
    media = Media()

    if request.POST["score"] == "":
        media.score = None
    else:
        media.score = float(request.POST["score"])

    if "num_episodes" in metadata and (request.POST["status"] == "Completed" or int(request.POST["progress"]) > metadata["num_episodes"]):
        media.progress = metadata["num_episodes"]
    elif request.POST["progress"] != "":
        media.progress = request.POST["progress"]
    else:
        media.progress = 0

    if request.POST["start"] != "":
        media.start_date = request.POST["start"]
    else:
        media.start_date = datetime.date.today()

    if request.POST["end"] != "":
        media.end_date = request.POST["end"]
    elif request.POST["status"] == "Completed":
        media.end_date = datetime.date.today()
    else:
        media.end_date = None

    media.media_id=metadata["id"]
    media.title=metadata["title"]
    media.user=request.user
    media.status=request.POST["status"]
    media.media_type = metadata["media_type"]

    media.api = metadata["api"]

    if metadata["image"] == "" or metadata["image"] == None:
        media.image = "images/none.svg"
    else:
        if media.api == "mal":
            img_temp = helpers.get_image_temp(metadata['image'])
            if media.media_type == "anime":
                media.image.save(f"anime-{metadata['image'].rsplit('/', 1)[-1]}", File(img_temp), save=False)
            elif media.media_type == "manga":
                media.image.save(f"manga-{metadata['image'].rsplit('/', 1)[-1]}", File(img_temp), save=False)
            img_temp.close()
        else:        
            img_temp = helpers.get_image_temp(f"https://image.tmdb.org/t/p/w92{metadata['image']}")
            media.image.save(f"tmdb-{metadata['image'].rsplit('/', 1)[-1]}", File(img_temp))
            img_temp.close()

    if "season" in request.POST:
        if request.POST["season"] == "all":
            seasons_list = []
            for season in range(1, metadata["number_of_seasons"] + 1):
                if "episode_count" in metadata["seasons"][season - 1] and media.status == "Completed":
                    seasons_list.append(Season(media=media, title=media.title, number=season, score=media.score, status=media.status, 
                                               progress=metadata["seasons"][season - 1]["episode_count"],
                                               start_date=media.start_date, end_date=media.end_date))
                else:
                    seasons_list.append(Season(media=media, title=media.title, number=season, score=media.score, status=media.status, progress=0,
                                               start_date=media.start_date, end_date=media.end_date))
            Season.objects.bulk_create(seasons_list)

        else:
            if request.POST["status"] == "Completed" and "episode_count" in metadata["seasons"][int(request.POST["season"]) - 1]:
                media.progress = metadata["seasons"][int(request.POST["season"]) - 1]["episode_count"]
                
            Season.objects.create(media=media, title=media.title, number=request.POST["season"], score=media.score, status=media.status,
                                  progress=media.progress, start_date=media.start_date, end_date=media.end_date)

    media.save()
    del request.session["metadata"]
    

def edit_media(request):
    metadata = request.session.get("metadata")
    if request.POST["score"] == "":
        score = None
    else:
        score = float(request.POST["score"])

    if request.POST["start"] != "":
        start_date = request.POST["start"]
    else:
        start_date = datetime.date.today()

    if request.POST["end"] != "":
        end_date = request.POST["end"]
    elif request.POST["status"] == "Completed":
        end_date = datetime.date.today()
    else:
        end_date = None

    media = Media.objects.get(
        media_id=metadata["id"],
        media_type=metadata["media_type"],
        user=request.user,
        api=metadata["api"],
    )

    if "season" in request.POST:
        if request.POST["season"] == "all":
            for season in range(1, metadata["number_of_seasons"] + 1):
                if "episode_count" in metadata["seasons"][season - 1] and request.POST["status"] == "Completed":
                    progress = metadata["seasons"][season - 1]["episode_count"]
                    Season.objects.update_or_create(media=media, number=season,
                                defaults={"title":metadata["title"], "score": score, "status": request.POST["status"],
                                          "progress": progress, "start_date":start_date, "end_date":end_date})
                else:
                    # don't update progress if it has a value
                    obj, created = Season.objects.get_or_create(media=media, number=season, 
                                defaults={"title":metadata["title"], "score": score, "status": request.POST["status"],
                                          "progress": 0, "start_date":start_date, "end_date":end_date})
                    if not created:
                        Season.objects.filter(media=media, number=season).update(score=score, status=request.POST["status"],
                                                                                 start_date=start_date, end_date=end_date)    
                                    
        else:
            # if media didn't have any seasons, create first season with the same data as the media
            if Season.objects.filter(media=media).count() == 0:
                Season.objects.create(media=media, title=media.title, number=1, score=media.score, status=media.status,
                                      progress=media.progress, start_date=media.start_date, end_date=media.end_date)

            metadata_curr_season = metadata["seasons"][int(request.POST["season"]) - 1]
            if "episode_count" in metadata_curr_season and (request.POST["status"] == "Completed" or int(request.POST["progress"]) > metadata_curr_season["episode_count"]):
                progress = metadata_curr_season["episode_count"]
            elif request.POST["progress"] != "":
                progress = request.POST["progress"]
            else:
                progress = 0

            Season.objects.update_or_create(media=media, number=request.POST["season"],
                        defaults={"title":metadata["title"], "score": score, "status": request.POST["status"],
                                    "progress": progress, "start_date":start_date, "end_date":end_date})

        seasons = Season.objects.filter(media=media)
        mean_score = seasons.aggregate(Avg('score'))['score__avg']
        progress_total = seasons.aggregate(Sum('progress'))['progress__sum']
        media.score = mean_score
        media.progress = progress_total
        media.status = request.POST["status"]
        media.start_date = seasons.aggregate(Min('start_date'))['start_date__min']
        media.end_date = seasons.aggregate(Max('end_date'))['end_date__max']

        media.save()
        
    else:
        if "num_episodes" in metadata and (request.POST["status"] == "Completed" or int(request.POST["progress"]) > metadata["num_episodes"]):
            progress = metadata["num_episodes"]
        elif request.POST["progress"] != "":
            progress = request.POST["progress"]
        else:
            progress = 0

        media.score = score
        media.progress = progress
        media.status = request.POST["status"]
        media.start_date = start_date
        media.end_date = end_date
        media.save()

    del request.session["metadata"]