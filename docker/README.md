# docker-webscrapbook

Docker for the remote server of the firefox extension webscrapbook. 
* Server Web: https://pypi.org/project/webscrapbook/
* Extension Firefox: https://github.com/danny0838/webscrapbook


### Create Container:
```
docker run --name webscrapbook -v /dokers/webscrapbook_data:/data -p 8080:8080/tcp vsc55/webscrapbook:latest
```
or
```
docker create --name webscrapbook -v /dokers/webscrapbook_data:/data -p 8080:8080/tcp vsc55/webscrapbook:latest
docker container start webscrapbook
```
