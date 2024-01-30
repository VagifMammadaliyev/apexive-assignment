ontime_env=$ONTIME_ENV
prod_env="PRODUCTION"
staging_env="STAGING"

center() {
    termwidth="$(tput cols)"
    padding="$(printf '%0.1s' ={1..500})"
    printf '%*.*s %s %*.*s\n' 0 "$(((termwidth-2-${#1})/2))" "$padding" "$1" 0 "$(((termwidth-1-${#1})/2))" "$padding"
}


update_repo() {
    if [ $1 == "$staging_env" ]
    then
        center "Deploying to staging"
        git fetch origin && git checkout staging && git reset --hard origin/staging
        return $?
    else
        center "Deploying to production"
        git fetch origin && git checkout production && git merge origin/master && git push
        return $?
    fi
}

build_containers() {
    if [ $1 == "$staging_env" ]
    then
        center "Building staging containers"
        docker-compose -f docker-compose-staging.yml up --build -d
        return $?
    else
        center "Building production containers"
        docker-compose -f docker-compose-production.yml up --build -d
        return $?
    fi
}

django_stuff() {
    center "Already done!"
    docker exec -it ontime-api bash -c "
        python manage.py makemigrations --merge --noinput &&
        python manage.py makemigrations &&
        python manage.py migrate &&
        python manage.py collectstatic --noinput &&
        python manage.py compilemessages
    "
    return $?
}

docker_cleanup() {
    center "You should clean after yoursel, PIG!"
    docker image prune -a --force
}

if [ ! -z "$ontime_env" ]
then

    if ! [[ "$ontime_env" == "$prod_env" || "$ontime_env" == "$staging_env" ]]
    then
        echo "Invalid ONTIME_ENV. It must be $prod_env or $staging_env"
        exit 1
    fi

    update_repo $ontime_env && build_containers $ontime_env && django_stuff $ontime_env && docker_cleanup
else
    echo "You have not set ONTIME_ENV variable. Set it to $prod_env or $staging_env."
    exit 1
fi


