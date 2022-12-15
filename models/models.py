import itertools
import json
from typing import Optional

import pydantic
import requests
import rhino3dm
from collection.multi_description import MultiDescriptor

from mm.conversions import rhino
from mm.pydantic_mm.models import Archive3dm, ComputeRequest, DataTreeParam, InnerTreeItem


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


def openarchive(path="/Users/andrewastakhov/PycharmProjects/mmodel/tests/data/L2-triangles.json"):
    with open(path, "r") as f:
        jdt = json.load(f)
        MultiDescriptor(jdt)["archive3dm"] = itertools.repeat(len(jdt), 70)
        return [Archive3dm(**r) for r in jdt]


req = ComputeRequest(
    pointer="c:/users/administrator/compute-deploy/match.gh",
    values=[
        DataTreeParam(
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


def writerh(bind_sequence, name="modeltest.3dm"):
    model = rhino3dm.File3dm()
    [model.Objects.Add(g) for g in bind_sequence["textdot"] + bind_sequence["geometry"]]
    model.Write(name, 7)
