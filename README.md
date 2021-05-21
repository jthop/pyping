# pyping
Dead Simple Monitoring

### To get up and running:

#### Take care of some docker stuff
* `docker volume create mongodb-pyping`
* `docker network create pyping`
* `docker network create traefik`

#### Now create some config files with the provided templates
* `cp app/config/setup.cfg.template app/config/setup.yml`
  * edit accordingly
* choose a docker-compose yaml from /examples
* edit for your environment and move to `./docker-compose.yml`

### coming soon:

* dns secvice_types
* more agent services