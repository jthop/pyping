# pyping
Simple Monitoring Server

### To get up and running:

#### Take care of some docker stuff
* `docker volume create mongodb-pyping`
* `docker network create pyping`
* `docker network create traefik`

#### Now create some config files with the provided templates
* `cp app/config/setup.cfg.template app/config/setup.yml`
  * edit accordingly
* `cp docker-compose.yml.template docker-compose.yml`
  * edit accordingly

### coming soon:

testing via https://github.com/robotframework/robotframework

healthchecks 
