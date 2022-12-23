import itertools
import itertools
import os
from json import JSONEncoder
from typing import Any

import requests
from collection.multi_description import MultiDescriptor

from mmcore.addons import rhino
from mmcore.utils.pydantic_mm.models import Archive3dm, ComputeJson


class NTEncoder(JSONEncoder):
    def default(self, o):
        if hasattr(o, "_asdict"):

            return o._asdict()
        else:
            try:
                return json.loads(json.dumps(self, o))
            except Exception as err:
                raise TypeError

    def encode(self, o):

        return JSONEncoder.encode(self, self.default(o))


class MaskArchive3dm(ComputeJson):
    type = "Rhino.Geometry.GeometryBase"
    data: list[Archive3dm]

    @classmethod
    def from_file(cls, path) -> 'MaskArchive3dm':
        return MaskArchive3dm(type="Rhino.Geometry.Brep",
                              data=[Archive3dm.from_3dm(f) for f in rhino.get_model_geometry(path)])


class GridArchive(ComputeJson):
    type = "System.String"
    data: list[list[Archive3dm]]


class CellingTypes(ComputeJson):
    type = "System.String"
    data = list[Any]

    @classmethod
    def from_file(cls, file) -> 'CellingTypes':
        return CellingTypes(data=json.load(file))


def openarchive(path=".../tests/data/L2-triangles.json"):
    with open(path, "r") as f:
        jdt = json.load(f)
        MultiDescriptor(jdt)["archive3dm"] = itertools.repeat(len(jdt), 70)
        return [Archive3dm(**r) for r in jdt]


def do_request(path="example.json", **kwargs):
    with open(path, "r") as fl:
        data = json.load(fl)
        if kwargs:
            data |= kwargs
        resp = requests.post(f"{os.getenv('RHINO_COMPUTE_URL')}/grasshopper", json=data, headers={
            "User-Agent": "compute.rhino3d.py/1.2.0",
            "Accept": "application/json",
            "RhinoComputeKey": os.getenv('RHINO_COMPUTE_APIKEY'),
        })
    # js = resp.json()
    return json.loads(json.loads(list(resp.json()["values"][0]['InnerTree'].values())[0][0]["data"]))


def writerh(bind_sequence, name="modeltest.3dm"):
    model = rhino3dm.File3dm()
    [model.Objects.Add(g) for g in bind_sequence["textdot"] + bind_sequence["geometry"]]
    return model


import json

import rhino3dm
from mmcore.collection.multi_description import MultiDescriptor, traverse
from collections import namedtuple, Counter

ColorARGB = namedtuple("ColorARGB", ["a", "r", "g", "b"])


@traverse
def dd(data):
    if "archive3dm" in data.keys():
        data["archive3dm"] = 70
        return rhino3dm.GeometryBase.Decode(data)


@traverse
def colors(color): return ColorARGB(*eval(color))


model = rhino3dm.File3dm()


@traverse
def write_rh(bind):
    txt = rhino3dm.TextDot(bind['tag'], rhino3dm.Point3d(*eval(bind['center'])))
    attrs = rhino3dm.ObjectAttributes()
    attrs.ObjectColor = tuple(bind['color'])
    attrs.ColorSource = rhino3dm.ObjectColorSource.ColorFromObject

    attrs2 = rhino3dm.ObjectAttributes()
    attrs2.ObjectColor = (70, 70, 70, 255) if bind['subtype'] == "1" else (170, 70, 20, 255)
    attrs2.ColorSource = rhino3dm.ObjectColorSource.ColorFromObject

    model.Objects.Add(bind['geometry'], attrs2)
    model.Objects.Add(txt, attrs)


def aaa():
    with open("/Users/andrewastakhov/PycharmProjects/mmodel/dumps/b1.json", "r") as f:
        daga = json.load(f)

    bind = MultiDescriptor(daga)
    # d = list(dd(bind["geometry"]))
    # bind["geometry"] = d

    bind["color"] = list(colors(bind["color"]))
    d = list(dd(bind["geometry"]))
    bind["geometry"] = d

    write_rh(bind)
    model.Write("data/b1.3dm", 7)

    def area(f):
        for i, v in f.items():
            yield i, v * 0.18

    import pandas as pd
    f = Counter(bind["tag"])
    ddf = pd.DataFrame([dict(f), dict(area(f))]).T

    ddf.to_csv("data/b1.csv")
