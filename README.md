# Pyang plugin for Swagger

Most of the code has been taken from the [Pyang-COP](https://github.com/ict-strauss/COP/tree/master/pyang_plugins) repository and modified to fit our requirements

[Pyang](https://github.com/mbj4668/pyang) is an extensible YANG validator and converter written in python.

It can be used to validate YANG modules for correctness, to transform YANG modules into other formats, and to generate code from the modules. We have written a pyang plugin to obtain the RESTCONF API from a yang model.

The RESTCONF API of the YANG model is interpreted with [Swagger](http://swagger.io/), which is a powerful framework for API description. This framework will be used to generate a Stub server for the YANG module.


##Install pyang

Download pyang [here](https://github.com/mbj4668/pyang/releases) (tested with version pyang-1.7.1)
Extract the archive to a folder of you choice.
Install pyang  by running the following command inside that folder:

```
sudo python setup.py install
```

### Copy the swagger plugin to pyang's plugin directory:

```
sudo cp pyang_plugins/swagger.py /usr/local/lib/python2.7/dist-packages/{pyang_directory}/plugins/
```

## Run pyang swagger plugin

```
pyang -f swagger -p modules modules/config-bridge.yang -o config-bridge-swagger.json

      --use the option '-p' to specify the path of the yang models for import purposes.
```

### Have a look at the auto-generated JSON output 

[config-bridge.json](./output/config-bridge.json)

### Have a look at the auto-generated Swagger API on swaggerhub.com 
[config-bridge-api](https://app.swaggerhub.com/apis/sebymiano/config-bridge_api/1.0.0)

License
-------
Copyright 2017 Politecnico di Torino.

Copyright 2015 CTTC.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at [apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
