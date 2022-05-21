#!/usr/bin/python3
# copyright (c) 2018- polygoniq xyz s.r.o.

import bpy
import numpy
import unittest
import mathutils


class WorldBoundingBox:
    """Bounding box that operates with world space coordinate system.

    If WorldBoundingBox is extended by object then min_x, max_x,... values are in world space,
    not object local space. When object moves after initialization of WorldBoundingBox,
    coordinate properties are not recomputed to match new object's position - this class does not
    store any reference to initialization objects.
    WorldBoundingBox computes boundaries even for instanced collection objects, that's advantage
    compared to bound_box property of bpy.types.Object.
    """

    def extend_by_point(self, point: mathutils.Vector):
        self.min_x = min(self.min_x, point.x)
        self.max_x = max(self.max_x, point.x)
        self.min_y = min(self.min_y, point.y)
        self.max_y = max(self.max_y, point.y)
        self.min_z = min(self.min_z, point.z)
        self.max_z = max(self.max_z, point.z)

    def extend_by_object(self, obj: bpy.types.Object,
                         parent_collection_matrix: mathutils.Matrix = mathutils.Matrix.Identity(4)):
        # matrix_world is matrix relative to object's blend.
        # Thus collection objects have offset inside colllection defined by their matrix_world.
        # We need to multiply parent_collection_matrix by obj.matrix_world in recursion
        # to get matrix relevant to top-most collection world space.
        obj_matrix = parent_collection_matrix @ obj.matrix_world
        # if object is a collection, it has bounding box ((0,0,0), (0,0,0), ...)
        # we need to manually traverse objects from collections and extend main bounding box
        # to contain all objects
        if obj.instance_type == 'COLLECTION':
            collection = obj.instance_collection
            for collection_obj in collection.objects:
                self.extend_by_object(collection_obj, obj_matrix)
        else:
            for corner in obj.bound_box:
                self.extend_by_point(obj_matrix @ mathutils.Vector(corner))

    def __init__(self, min_x: float = float("inf"), max_x: float = float("-inf"),
                 min_y: float = float("inf"), max_y: float = float("-inf"),
                 min_z: float = float("inf"), max_z: float = float("-inf")):
        self.min_x = min_x
        self.max_x = max_x
        self.min_y = min_y
        self.max_y = max_y
        self.min_z = min_z
        self.max_z = max_z

    def get_eccentricity(self):
        """Returns relative eccentricity in each axis.
        """
        return mathutils.Vector((
            (self.max_x - self.min_x) / 2.0,
            (self.max_y - self.min_y) / 2.0,
            (self.max_z - self.min_z) / 2.0
        ))

    def get_center(self):
        return mathutils.Vector((self.min_x, self.min_y, self.min_z)) + self.get_eccentricity()

    def __str__(self):
        return (
            f"Bounding box \n"
            f"X = ({self.min_x}, {self.max_x}) \n"
            f"Y = ({self.min_y}, {self.max_y}) \n"
            f"Z = ({self.min_z}, {self.max_z})"
        )


def plane_from_points(points):
    assert len(points) == 3
    p1, p2, p3 = points

    v1 = p3 - p1
    v2 = p2 - p1

    normal = numpy.cross(v1, v2)
    normal_magnitude = numpy.linalg.norm(normal)
    normal /= normal_magnitude
    offset = numpy.dot(normal, p3)
    centroid = numpy.sum(points, 0) / len(points)

    return (normal, offset, centroid)


def fit_plane_to_points(points):
    assert len(points) >= 3
    return plane_from_points(points[:3])

    # TODO: This is borked :-(
    centroid = numpy.sum(points, 0) / len(points)
    centered_points = points - centroid
    svd = numpy.linalg.svd(numpy.transpose(centered_points))
    plane_normal = svd[0][2]
    # now that we have the normal let's fit the centroid to the plane to find the offset
    offset = numpy.dot(plane_normal, centroid)
    return (plane_normal, offset, centroid)


class PlaneFittingTest(unittest.TestCase):
    def test_3pts(self):
        # unit plane - (0, 0, 1), 0
        normal, offset, _ = fit_plane_to_points([(1, -1, 0), (-1, 0, 0), (0, 1, 0)])
        self.assertAlmostEqual(normal[0], 0)
        self.assertAlmostEqual(normal[1], 0)
        self.assertAlmostEqual(normal[2], 1)
        self.assertAlmostEqual(offset, 0)

        normal, offset, _ = fit_plane_to_points([(2, -2, 0), (-1, 0, 0), (0, 1, 0)])
        self.assertAlmostEqual(normal[0], 0)
        self.assertAlmostEqual(normal[1], 0)
        self.assertAlmostEqual(normal[2], 1)
        self.assertAlmostEqual(offset, 0)

        # offset unit plane - (0, 0, 1), 1
        normal, offset, _ = fit_plane_to_points([(2, -2, 1), (-1, 0, 1), (0, 1, 1)])
        self.assertAlmostEqual(normal[0], 0)
        self.assertAlmostEqual(normal[1], 0)
        self.assertAlmostEqual(normal[2], 1)
        self.assertAlmostEqual(offset, 1)

    def test_4pts(self):
        # unit plane - (0, 0, 1), 0
        normal, offset, _ = fit_plane_to_points([(1, -1, 0), (-1, 0, 0), (0, 1, 0), (1, 1, 0)])
        self.assertAlmostEqual(normal[0], 0)
        self.assertAlmostEqual(normal[1], 0)
        self.assertAlmostEqual(normal[2], 1)
        self.assertAlmostEqual(offset, 0)

        # can't fit precisely! unit plane - (0, 0, 1), 0
        large = 100000000000
        normal, offset, _ = fit_plane_to_points(
            [(-large, -large, 0.1), (-large, large, -0.1), (large, -large, 0.1), (large, large, -0.1)])
        self.assertAlmostEqual(normal[0], 0)
        self.assertAlmostEqual(normal[1], 0)
        self.assertAlmostEqual(normal[2], 1)
        self.assertAlmostEqual(offset, 0)


if __name__ == "__main__":
    unittest.main()
