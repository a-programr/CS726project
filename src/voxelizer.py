from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

import numpy as np
import glob
import os

from renderutils import Camera
from renderutils import GLWindow
from renderutils import RenderUtils
from renderutils import progress

from mesh import Mesh


def project(vertices, axis):
	vmin = np.inf
	vmax = -np.inf
	for v in vertices:
		val = v.dot(axis)
		if (val < vmin):
			vmin = val
		if (val > vmax):
			vmax = val

	return vmin, vmax


class Box(object):
	def __init__(self, center, size):
		self.center = center
		self.size = size

	def contains_point(self, point):
		x0 = self.center[0] - self.size/2.
		x1 = self.center[0] + self.size/2.

		y0 = self.center[1] - self.size/2.
		y1 = self.center[1] + self.size/2.

		z0 = self.center[2] - self.size/2.
		z1 = self.center[2] + self.size/2.

		inside = x0 < point[0] < x1 and y0 < point[1] < y1 and\
			z0 < point[2] < z1

		return inside

	def contains_triangle(self, triangle):
		normals = np.eye(3)
		start = self.center - (self.size/2.)*np.ones(3)
		end = self.center + (self.size/2.)*np.ones(3)
		h = self.size/2.

		box_vertices = np.array([
			self.center + np.array([-h, -h, -h]),
			self.center + np.array([-h, -h, h]),
			self.center + np.array([-h, h, -h]),
			self.center + np.array([-h, h, h]),
			self.center + np.array([h, -h, -h]),
			self.center + np.array([h, -h, h]),
			self.center + np.array([h, h, -h]),
			self.center + np.array([h, h, h])])

		for n_i, n in enumerate(normals):
			trimin, trimax = project(triangle, n)
			if trimax < start[n_i] or trimin > end[n_i]:
				return False

		triangle_normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
		triangle_offset = triangle_normal.dot(triangle[0])
		boxmin, boxmax = project(box_vertices, triangle_normal)
		if boxmax < triangle_offset or boxmin > triangle_offset:
			return False

		triangle_edges = np.array([
			triangle[0] - triangle[1],
			triangle[1] - triangle[2],
			triangle[2] - triangle[0]])

		for i in range(3):
			for j in range(3):
				axis = np.cross(triangle_edges[i], normals[j])
				boxmin, boxmax = project(box_vertices, axis)
				trimin, trimax = project(triangle, axis)
				if boxmax <= trimin or boxmin >= trimax:
					return False

		return True

	def contains_mesh(self, mesh):
		for i in xrange(mesh.num_faces()):
			if self.contains_triangle(mesh.get_triangle(i)):
				return True
		return False


def center_samples(s):
	return s-np.mean(s, 0)


def voxelize(mesh, size=np.array([64., 64., 64.]), dims=np.array([2.5, 2.5, 2.5])):

	xs = np.linspace(-dims[0]/2., dims[0]/2., int(size[0])+1)
	ys = np.linspace(-dims[1]/2., dims[1]/2., int(size[1])+1)
	zs = np.linspace(-dims[2]/2., dims[2]/2., int(size[2])+1)

	samples = center_samples(np.array(mesh.get_samples(10000)))

	voxels, _ = np.histogramdd(samples, bins=(xs, ys, zs))
	voxels = np.clip(voxels, 0, 1)

	return voxels


class MeshViewer(GLWindow):

	def __init__(self, window_name="Mesh Viewer", window_size=(640, 640)):
		super(MeshViewer, self).__init__(window_name, window_size)
		self.camera = Camera()
		self.origin = np.array([0, 0, 0])

		self.mesh = Mesh("models/chairs/chair_0305.off")
		self.samples = self.mesh.get_samples(1e3)
		self.samples = center_samples(self.samples)

		self.camera_speed = 1/100.
		self.initialize()
		self.action = ""

		self.prev_x = 0
		self.prev_y = 0

		voxelize(self.mesh)

		glutMainLoop()

	def mouse(self, button, state, x, y):
		if button == GLUT_LEFT_BUTTON:
			self.action = "MOVE_CAMERA"

	def motion(self, x, y):
		if self.action == "MOVE_CAMERA":
			dx = self.prev_x - x
			dy = self.prev_y - y
			self.camera.theta -= dx * self.camera_speed
			self.camera.phi += dy * self.camera_speed
			self.prev_x = x
			self.prev_y = y

	def initialize(self):
		MAX_COORD = 2.

		glEnable(GL_DEPTH_TEST)
		glDepthFunc(GL_LESS)
		glClearColor(1.0, 1.0, 1.0, 0.0)
		glClearDepth(1.0)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(-MAX_COORD, MAX_COORD, -MAX_COORD, MAX_COORD,
				0.1, 1000.0)

		glShadeModel(GL_SMOOTH)

	def display(self):
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		self.camera.place()
		RenderUtils.color([1, 1, 0])
		self.mesh.draw()
		RenderUtils.color([0, 0, 1])
		RenderUtils.draw_points(self.samples)
		# RenderUtils.color([0, 0, 1])
		# self.mesh.draw_normals()


def volume_to_points(volume, threshold=0, dim=[2., 2., 2.]):
	o = np.array([-dim[0]/2., -dim[1]/2., -dim[2]/2.])
	step = np.array([dim[0]/volume.shape[0], dim[1]/volume.shape[1], dim[2]/volume.shape[2]])
	points = []
	for x in range(volume.shape[0]):
		for y in range(volume.shape[1]):
			for z in range(volume.shape[2]):
				pos = o + np.array([x, y, z]) * step
				if volume[x, y, z] > threshold:
					points.append(pos)
	return points

def volume_to_conf(volume, dim=[2., 2., 2.]):
	o = np.array([-dim[0]/2., -dim[1]/2., -dim[2]/2.])
	step = np.array([dim[0]/volume.shape[0], dim[1]/volume.shape[1], dim[2]/volume.shape[2]])
	points = []
	conf = []
	for x in range(3,volume.shape[0]-3):
		for y in range(3,volume.shape[1]-3):
			for z in range(3,volume.shape[2]-3):
				pos = o + np.array([x, y, z]) * step
				points.append(pos)
				conf.append(volume[x, y, z])
	return points, conf

def volume_to_cubes(volume, threshold=0, dim=[2., 2., 2.]):
	o = np.array([-dim[0]/2., -dim[1]/2., -dim[2]/2.])
	step = np.array([dim[0]/volume.shape[0], dim[1]/volume.shape[1], dim[2]/volume.shape[2]])
	points = []
	faces = []
	for x in range(1, volume.shape[0]-1):
		for y in range(1, volume.shape[1]-1):
			for z in range(1, volume.shape[2]-1):
				pos = o + np.array([x, y, z]) * step
				if volume[x, y, z] > threshold:
					vidx = len(points)+1
					POS = pos + step*0.95
					xx = pos[0]
					yy = pos[1]
					zz = pos[2]
					XX = POS[0]
					YY = POS[1]
					ZZ = POS[2]
					points.append(np.array([xx, yy, zz]))
					points.append(np.array([xx, YY, zz]))
					points.append(np.array([XX, YY, zz]))
					points.append(np.array([XX, yy, zz]))
					points.append(np.array([xx, yy, ZZ]))
					points.append(np.array([xx, YY, ZZ]))
					points.append(np.array([XX, YY, ZZ]))
					points.append(np.array([XX, yy, ZZ]))
					faces.append(np.array([vidx, vidx+1, vidx+2, vidx+3]))
					faces.append(np.array([vidx, vidx+4, vidx+5, vidx+1]))
					faces.append(np.array([vidx, vidx+3, vidx+7, vidx+4]))
					faces.append(np.array([vidx+6, vidx+2, vidx+1, vidx+5]))
					faces.append(np.array([vidx+6, vidx+5, vidx+4, vidx+7]))
					faces.append(np.array([vidx+6, vidx+7, vidx+3, vidx+2]))
	return points, faces

def write_points_obj(path, points):
	f = open(path, 'w')
	for p in points:
		f.write("v {} {} {}\n".format(p[0], p[1], p[2]))

def write_cubes_obj(path, points, faces):
	f = open(path, 'w')
	for p in points:
	  f.write("v {} {} {}\n".format(p[0], p[1], p[2]))
	for q in faces:
	  f.write("f {} {} {} {}\n".format(q[0], q[1], q[2], q[3]))

def write_conf_obj(path, points, conf):
	f = open(path, 'w')
	for p in points:
	  f.write("v {} {} {}\n".format(p[0], p[1], p[2]))
	for c in conf:
	  f.write("vc {}\n".format(c[0]))

if __name__ == '__main__':
	category_path = os.getcwd() + "/ModelNet10"
	categories = os.listdir(category_path)
	print(categories)
	for category in categories:
		category_npy_path = category_path + "/" + category + "_npy"
		try:
			os.mkdir(category_npy_path)
		except OSError as error:
			print(error)
		# os.mkdir(category_npy_path)
		# category_files = os.listdir(category_path + "/" + category)
		category_files_path = "ModelNet10/" + category + "/*.off"
		print(category_files_path)
		mesh_files_paths = glob.glob(category_files_path)
		mesh_files = os.listdir(category_path + "/" + category)
		total = len(mesh_files_paths)
		count = 0
		print("total:" + str(total))
		for i, mf in enumerate(mesh_files_paths):
			print(mf)
			print(mesh_files[i])
			m = Mesh(mf)
			vs = voxelize(m)
			pts = volume_to_points(vs)
			# path = mf.split('.')[0]
			name = mesh_files[i].split('.')[0]
			np.save(category_npy_path + "/" + name+'.npy', vs)
			# print(path)
			# write_points_obj(path+'.obj', pts)
			progress(count, total)
			count += 1
