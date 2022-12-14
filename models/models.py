import itertools
import json
from typing import Any, Optional

import pydantic
import requests
import rhino3dm
from pydantic import BaseModel
from pydantic import ConstrainedStr

from collection.multi_description import MultiDescriptor
from conversions import rhino


class SnakeCaseName(ConstrainedStr):
    strip_whitespace = True
    to_upper = False
    to_lower = True
    min_length: int | None = None
    max_length: int | None = None
    curtail_length: int | None = None
    regex: int | None = None
    strict = False


class Attributes(BaseModel):
    name: SnakeCaseName


class RhinoVersion(int):
    def __new__(cls, v):
        return int.__new__(cls, 70)


class RhinoBase64str(str):
    def __repr__(self):
        return str.__repr__(self)[:10] + " ... " + str.__repr__(self)[-10:]

    def __str__(self):
        return self.__repr__()


class Archive3dm(pydantic.BaseModel):
    opennurbs: int
    version: int
    archive3dm: RhinoVersion
    data: str

    @classmethod
    def from_3dm(cls, data3dm) -> 'Archive3dm':
        return cls(**rhino.RhinoEncoder().default(data3dm))

    def to_3dm(self) -> dict | rhino3dm.CommonObject | Any:
        return rhino.RhinoDecoder().decode(self.data)

    def __repr__(self):
        ss = super().__repr__().split("data")
        return ss[0] + "data: ... ')"

    def __str__(self):
        ss = super().__str__().split("data")
        return ss[0] + "data: ... ')"


class Grid(list[list[Archive3dm]]):
    ...


class FlatGrid(list[Archive3dm]):
    ...


class Mask3dmAttributes(pydantic.BaseModel):
    type: str
    data: list[Archive3dm]

    @classmethod
    def from_file(cls, path) -> 'Mask3dmAttributes':
        return Mask3dmAttributes(type="Rhino.Geometry.Brep",
                                 data=[Archive3dm.from_3dm(f) for f in rhino.get_model_geometry(path)])


class Mask3dm(pydantic.BaseModel):
    type: str = "Mask3dm"
    primary: str
    masked_type: str = "inside"
    attributes: Mask3dmAttributes


class SpatialTypology(list[tuple[tuple[str], tuple[float, float, float]]]):
    @classmethod
    def from_file(cls, path) -> 'SpatialTypology':
        with open(path, "r") as f:
            data = json.load(f)
            return SpatialTypology(list(data))


class RequestAttributes(pydantic.BaseModel):
    masks: Optional[list[Mask3dm]]
    types: Optional[SpatialTypology]
    grid: Grid | FlatGrid | list[Archive3dm] | list[list[Archive3dm]]


class ComputeInputArchive(pydantic.BaseModel):
    type: str = "ComputeInputArchive"
    primary: str
    attributes: RequestAttributes


class InnerTreeItem(pydantic.BaseModel):
    type: str
    data: str


class DTreeParam(pydantic.BaseModel):
    ParamName: str
    InnerTree: dict[str, list[InnerTreeItem]]


class ComputeStuff(pydantic.BaseModel):
    pointer: str
    values: list[DTreeParam]


def openarchive(path="/Users/andrewastakhov/PycharmProjects/mmodel/tests/data/L2-triangles.json"):
    with open(path, "r") as f:
        jdt = json.load(f)
        MultiDescriptor(jdt)["archive3dm"] = itertools.repeat(len(jdt), 70)
        return [Archive3dm(**r) for r in jdt]


req = ComputeStuff(
    pointer="c:/users/administrator/compute-deploy/match.gh",
    values=[
        DTreeParam(
            ParamName="input",
            InnerTree={
                "0": [
                    InnerTreeItem(
                        type="System.String",
                        data=ComputeInputArchive(
                            primary="L2",
                            attributes=RequestAttributes(
                                types=SpatialTypology.from_file(
                                    "/Users/andrewastakhov/PycharmProjects/mmodel/dumps/L2.json"),
                                masks=[Mask3dm(
                                    primary="stage",
                                    attributes=Mask3dmAttributes.from_file(
                                        "/Users/andrewastakhov/PycharmProjects/mmodel/lahta/data/L2cutmask.3dm")
                                )
                                ],
                                grid=openarchive()

                            )
                        ).json()
                    )
                ]
            }
        )
    ]

)


def do_request(path="example.json", **kwargs):
    with open(path, "r") as fl:
        data = json.load(fl)
        if kwargs:
            data |= kwargs
        resp = requests.post("http://79.143.24.242:8080/grasshopper", json=data, headers={
            "User-Agent": "compute.rhino3d.py/1.2.0",
            "Accept": "application/json",
            "RhinoComputeKey": "84407047-8380-441c-9c76-a07ca394b88e",
        })
    # js = resp.json()
    return json.loads(json.loads(list(resp.json()["values"][0]['InnerTree'].values())[0][0]["data"]))


data = do_request()
binded = MultiDescriptor(data)
geom = rhino.DecodeToCommonObject(binded["geometry"])


def writerh(binded, geom):
    model = rhino3dm.File3dm()
    [model.Objects.Add(g) for g in binded["textdot"] + geom]
    model.Write("modeltest.3dm")
