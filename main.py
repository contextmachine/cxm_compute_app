# This is a sample Python script.
import hashlib
import time
from enum import Enum

import pydantic
import redis_om
from fastapi import FastAPI, UploadFile
from starlette.responses import HTMLResponse

from mmcore.baseitems import Matchable
from mmcore.collection.multi_description import SequenceBinder
from mmcore.utils.pydantic_mm.models import ComputeRequest, ComputeResponse, DataTreeParam, InnerTreeItem
from mmcore.utils.redis_tools import topickle
from models import *

REDIS_URL = "redis://localhost:6380"
conn = redis_om.get_redis_connection(url=REDIS_URL, db=1)


# Press ⌃R to execute it or replace it with your code.
# Press Double ⇧ to search everywhere for classes, files, tool windows, actions, and settings.
class RequestSchema:
    params = {}

    def __init__(self):
        super().__init__()

    def __set_name__(self, owner, name):
        self.name = name

        setattr(owner, "_" + name, self)

    def prop(self, inst, owm):
        for name in self.params.keys():
            yield DataTreeParam(
                ParamName=name,
                InnerTree={
                    "0": [
                        owm.__getattribute__(inst, name)
                    ]
                }
            )

    def __get__(self, instance, owner):
        if instance is None:
            return self
        else:
            return ComputeRequest(pointer=owner.pointer, values=list(self.prop(instance, owner)))


class FlatCelling(MultiDescriptor):

    def __init__(self, inputs_path="./", endpoint="http://79.143.24.242:8080/grasshopper", **kw):
        self.input_path = inputs_path
        self.request = kw
        self.endpoint = endpoint
        self.request |= self.static
        super().__init__(self.do_request())
        self["geometry"] = rhino.DecodeToCommonObject(self["geometry"])

    @property
    def static(self):
        with open(self.input_path, "r") as fl:
            return json.load(fl)

    def do_request(self):
        ts = time.time()
        resp = requests.post(self.endpoint, json=self.request, headers={
            "User-Agent": "compute.rhino3d.py/1.2.0",
            "Accept": "application/json",
            "RhinoComputeKey": "84407047-8380-441c-9c76-a07ca394b88e",
        })
        # js = resp.json()
        return {"data": json.loads(json.loads(list(resp.json()["values"][0]['InnerTree'].values())[0][0]["data"])),
                "metadata": {
                    "timestamp": {
                        "start": ts,
                        "delta":
                            divmod(time.time() - ts, 60)
                    }
                }}


def commit(ex, p="L1", n="mask", i=2):
    return conn.xadd(f"lahta:celling:{p}:{n}", {
        "type": json.dumps(ex["values"][i]["InnerTree"]['0'][0]["type"]).encode(),
        "data": json.dumps(ex["values"][i]["InnerTree"]['0'][0]["data"]).encode()
    })


RedisStreamItem = namedtuple("RedisStreamItem", ["id", "data"])


def cxm_xrevrange(name, count=1, schema=RedisStreamItem):
    return [schema(i, dt) for (i, dt) in conn.xrevrange(name, "+", "-", count)]


def cxm_xlast(name, schema=InnerTreeItem):
    c = conn.xrevrange(name, "+", "-", 1)
    # print(c, name)
    [(i, data)] = c
    return schema(**dict(type=data["type"], data=data["data"]))


'1671708912950-0'
'1671708943697-0'


class RedisProperty:

    def __set_name__(self, owner, name):
        self.name = name
        owner.request.params[name] = self

    def __get__(self, instance, owner):
        return cxm_xlast(f'{instance.stream_name}:{self.name}', schema=instance.redis_schema)

    def __set__(self, instance, value: InnerTreeItem):
        d = value.dict()
        d["data"] = json.dumps(d["data"]) if not isinstance(value.dict()["data"], str) else d["data"]
        _id = conn.xadd(f'{instance.stream_name}:{self.name}', d)

        instance.__dict__["_" + self.name + "_id"] = _id


class Inp(pydantic.BaseModel):
    part: str
    types: dict[str, Any]
    mask: list[list[Archive3dm]]

    def commit(self, ex, n="mask", i=2):
        return conn.xadd(f"lahta:celling:{self.part}:{n}", {

            "type": json.dumps(ex["values"][i]["InnerTree"]['0'][0]["type"]).encode(),
            "data": json.dumps(ex["values"][i]["InnerTree"]['0'][0]["data"]).encode()
        })


class FlatCellingPart(Matchable):
    redis_schema = InnerTreeItem
    conn = conn
    part = RedisProperty()
    request = RequestSchema()
    mask = RedisProperty()
    types = RedisProperty()
    grid = RedisProperty()

    def __init__(self, prt):
        super().__init__()
        self._part = prt.lower()

    pointer = "c:/users/administrator/compute-deploy/match.gh"
    _stream_primary_name = "lahta:celling"

    @property
    def stream_name(self):
        return f"{self._stream_primary_name}:{self._part}"

    @property
    def stream_primary_name(self):
        return self._stream_primary_name

    @stream_primary_name.setter
    def stream_primary_name(self, value):
        self._stream_primary_name = value

    @property
    def endpoint(self):
        return self.conn.get(f'{self.stream_primary_name}:secrets:compute:endpoint')

    @property
    def apikey(self):
        return self.conn.get(f'{self.stream_primary_name}:secrets:compute:apikey')

    def do_request(self):
        ts = time.time()
        resp = requests.post(f'{self.endpoint}/grasshopper', json=self.request.dict(), headers={
            "User-Agent": "compute.rhino3d.py/1.2.0",
            "Accept": "application/json",
            "RhinoComputeKey": self.apikey,
        })
        # js = resp.json()
        self._resp = resp

        self._dat = {"data": json.loads(json.loads(list(resp.json()["values"][0]['InnerTree'].values())[0][0]["data"])),
                     "metadata": {
                         "timestamp": {
                             "start": ts,
                             "delta": divmod(time.time() - ts, 60)
                         }
                     }
                     }
        conn.xadd(f"lahta:celling:{self.part}",
                  {
                      "data": topickle(self),
                      "type": "pkl",
                      "metadata": {
                          "timestamp": time.time_ns()
                      }}
                  )
        return ComputeResponse(**self._dat)

    @property
    def table(self):
        return SequenceBinder(self._dat["data"])

    def to_3dm(self, model_name=None):
        return writerh(self.table, f'hex(self.__hash__()).3dm' if model_name is None else model_name)

    def __hash__(self):
        return int(self.sha256().hexdigest(), 32)

    def sha256(self):
        return hashlib.sha256(self._resp.text.encode())


celling = FastAPI()


class Params(str, Enum):
    part = "part"
    types = "types"
    mask = "mask"
    grid = "grid"


class Parts(str, Enum):
    L1 = "l1"
    B1 = "b1"
    L2 = "l2"


@celling.post("/uploadfile/{part}/{name}")
async def create_upload_masks(name: Params, part: Parts, file: UploadFile):
    celling_part = FlatCellingPart(part)
    content = await file.read()
    match name:
        case Params.mask:
            celling_part.mask = MaskArchive3dm(type="Rhino.Geometry.GeometryBase",
                                               data=[Archive3dm.from_3dm(obj) for obj in
                                                     rhino.get_model_geometry_from_buffer(content)])
        case Params.types:
            print(content)
            celling_part.types = InnerTreeItem(type="System.String", data=content)
        case Params.grid:
            celling_part.grid = GridArchive(type="System.String", data=json.loads(content))

    return {"msg": "commit succsess"}


@celling.post("/commit/{part}/{name}")
async def commit(name: Params, part: Parts, data: ComputeJson | MaskArchive3dm | CellingTypes | GridArchive):
    celling_part = FlatCellingPart(part)
    match name:
        case Params.mask:
            celling_part.mask = data.transform_json()
        case Params.types:
            celling_part.types = data.transform_json()
        case Params.grid:
            celling_part.grid = data.transform_json()
    return {"msg": "update succsess"}


@celling.get("/solve/{part}", response_model=ComputeResponse)
async def solve(part: Parts):
    celling_part = FlatCellingPart(part)
    celling_part.do_request()


@celling.get("/")
async def main():
    content = """
<body>
<form action="/uploadfile/" enctype="multipart/form-data" method="post">
<input name="file" type="file" multiple>
<input type="submit">
</form>
</body>
    """
    return HTMLResponse(content=content)

# Press the green button in the gutter to run the script.

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
