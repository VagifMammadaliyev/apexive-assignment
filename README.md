# OnTime.az API

[![Run in Postman](https://run.pstmn.io/button.svg)](https://app.getpostman.com/run-collection/045a6bc535782dd2d0b3)

## Start application

To get this application running follow these steps:

```bash
cd ontime-project/  # or whatever you have named project folder

# start postgres
docker-compose up -d postgres  # wait a couple of seconds before proceeding

# check that postgres is running
docker ps

# start application itself
docker-compose up -d api

# make migrations for database
docker exec -it ontime-api bash

# you must be inside docker container
root$ python manage.py makemigrations --merge && python manage.py makemigrations && python manage.py migrate
root$ exit

# you are now outside and can go to http://localhost. If you get a 404 error, then everything is working
```
