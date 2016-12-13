# -*- coding: utf8 -*-
# python
# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>


bl_info = {
    'name': 'Texture Paint plus',
    'author': 'Bart Crouch, scorpion81, Spirou4D, CDMJ',
    'version': (2, 20),
    'blender': (2, 73, 0),
    'location': 'Paint editor > 3D view',
    'warning': '',
    'description': 'Several improvements for Texture Paint mode',
    'wiki_url': '',
    'tracker_url': '',
    'category': 'Paint'}


import bgl
import blf
import bpy
import mathutils
import os
import time
import copy
import math
from bpy_extras.io_utils import ImportHelper
from bpy.types import Operator, Menu, Panel, UIList

#################################################
#                                               #
# Functions          for                        #
# '''Sync selection from uv-editor to 3d-view'''#
#################################################


# draw in 3d-view =>OK!
def draw_callback(self, context):
    r, g, b = context.tool_settings.image_paint.brush.cursor_color_add
    #x0, y0, x1, y1 = context.window_manager["straight_line"]
    start = self.stroke[0]
    end = self.stroke[-1]

    x0 = start["mouse"][0]
    y0 = start["mouse"][1]

    x1 = end["mouse"][0]
    y1 = end["mouse"][1]

    # draw straight line
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(r, g, b, 1.0)
    bgl.glBegin(bgl.GL_LINE_STRIP)
    bgl.glVertex2i(x0, y0)
    bgl.glVertex2i(x1, y1)
    bgl.glEnd()
    # restore opengl defaults
    bgl.glDisable(bgl.GL_BLEND)
    bgl.glColor4f(0.0, 0.0, 0.0, 1.0)


# return a list of all images that are being displayed in an editor =>OK!
def get_images_in_editors(context):
    images = []
    for area in context.screen.areas:
        if area.type != 'IMAGE_EDITOR':
            continue
        for space in area.spaces:
            if space.type != 'IMAGE_EDITOR':
                continue
            if space.image:
                images.append(space.image)
                area.tag_redraw()

    return(images)


# calculate for 3d-view =>OK!
def sync_calc_callback(self, context, area, region):
    mid_x = region.width/2.0
    mid_y = region.height/2.0
    width = region.width
    height = region.height

    region_3d = False
    for space in area.spaces:
        if space.type == 'VIEW_3D':
            region_3d = space.region_3d
    if not region_3d:
        return

    view_mat = region_3d.perspective_matrix
    ob_mat = context.active_object.matrix_world
    total_mat = view_mat * ob_mat
    mesh = context.active_object.data

    def transform_loc(loc):
        vec = total_mat * loc
        vec = mathutils.Vector([vec[0]/vec[3], vec[1]/vec[3], vec[2]/vec[3]])
        x = int(mid_x + vec[0]*width/2.0)
        y = int(mid_y + vec[1]*height/2.0)

        return([x, y])

    # vertices
    locs = [mesh.vertices[v].co.to_4d() for v in self.overlay_vertices]
    self.position_vertices = []
    for loc in locs:
        self.position_vertices.append(transform_loc(loc))

    # edges
    locs = [[mesh.vertices[mesh.edges[edge].vertices[0]].co.to_4d(),
        mesh.vertices[mesh.edges[edge].vertices[1]].co.to_4d()] \
        for edge in self.overlay_edges]
    self.position_edges = []
    for v1, v2 in locs:
        self.position_edges.append(transform_loc(v1))
        self.position_edges.append(transform_loc(v2))

    # faces
    locs = [[mesh.vertices[mesh.faces[face].vertices[0]].co.to_4d(),
        mesh.vertices[mesh.faces[face].vertices[1]].co.to_4d(),
        mesh.vertices[mesh.faces[face].vertices[2]].co.to_4d(),
        mesh.vertices[mesh.faces[face].vertices[3]].co.to_4d(),] \
        for face in self.overlay_faces]
    self.position_faces = []
    for v1, v2, v3, v4 in locs:
        self.position_faces.append(transform_loc(v1))
        self.position_faces.append(transform_loc(v2))
        self.position_faces.append(transform_loc(v3))
        self.position_faces.append(transform_loc(v4))


# draw in 3d-view  =>OK!
def sync_draw_callback(self, context):
    # polling
    if context.mode != "EDIT_MESH":
        return

    # draw vertices
    bgl.glColor4f(1.0, 0.0, 0.0, 1.0)
    bgl.glPointSize(4)
    bgl.glBegin(bgl.GL_POINTS)
    for x, y in self.position_vertices:
        bgl.glVertex2i(x, y)
    bgl.glEnd()

    # draw edges
    bgl.glColor4f(1.0, 0.0, 0.0, 1.0)
    bgl.glLineWidth(1.5)
    bgl.glBegin(bgl.GL_LINES)
    for x, y in self.position_edges:
        bgl.glVertex2i(x, y)
    bgl.glEnd()
    bgl.glLineWidth(1)

    # draw faces
    bgl.glEnable(bgl.GL_BLEND)
    bgl.glColor4f(1.0, 0.0, 0.0, 0.3)
    bgl.glBegin(bgl.GL_QUADS)
    for x, y in self.position_faces:
        bgl.glVertex2i(x, y)
    bgl.glEnd()
    bgl.glDisable(bgl.GL_BLEND)


# draw in image-editor =>OK!
def sync_draw_callback2(self, context):
    # polling
    if context.mode != "EDIT_MESH":
        return

    # draw vertices
    bgl.glColor4f(1.0, 0.0, 0.0, 1.0)
    bgl.glPointSize(6)
    bgl.glBegin(bgl.GL_POINTS)
    for x, y in self.position2_vertices:
        bgl.glVertex2f(x, y)
    bgl.glEnd()


# draw paint tool and blendmode in 3d-view =>?
def toolmode_draw_callback(self, context):
    # polling
    if context.mode != 'PAINT_TEXTURE':
        return

    # draw
    if context.region:
        main_y = context.region.height - 32
    else:
        return
    blend_dic = {"MIX": "Mix",
        "ADD": "Add",
        "SUB": "Subtract",
        "MUL": "Multiply",
        "LIGHTEN": "Lighten",
        "DARKEN": "Darken",
        "ERASE_ALPHA": "Erase Alpha",
        "ADD_ALPHA": "Add Alpha",
        "OVERLAY": "Overlay",
        "HARDLIGHT": "Hard light",
        "COLORBURN": "Color burn",
        "LINEARBURN": "Linear burn",
        "COLORDODGE": "Color dodge",
        "SCREEN": "Screen",
        "SOFTLIGHT": "Soft light",
        "PINLIGHT": "Pin light",
        "VIVIDLIGHT": "Vivid light",
        "LINEARLIGHT": "Linear light",
        "DIFFERENCE": "Difference",
        "EXCLUSION": "Exclusion",
        "HUE": "Hue",
        "SATURATION": "Saturation",
        "LUMINOSITY": "Luminosity",
        "COLOR": "Color"
        }
    brush = context.tool_settings.image_paint.brush
    text = brush.name + " - " + blend_dic[brush.blend]

    # text in top-left corner
    bgl.glColor3f(0.6, 0.6, 0.6)
    blf.position(0, 21, main_y, 0)
    blf.draw(0, text)

    # text above brush
    dt = time.time() - context.window_manager["tpp_toolmode_time"]
    if dt < 1:
        if "tpp_toolmode_brushloc" not in context.window_manager:
            return
        brush_x, brush_y = context.window_manager["tpp_toolmode_brushloc"]
        brush_x -= blf.dimensions(0, text)[0] / 2
        bgl.glColor4f(0.6, 0.6, 0.6, min(1.0, (1.0 - dt)*2))
        blf.position(0, brush_x, brush_y, 0)
        blf.draw(0, text)


# add ID-properties to window-manager
def init_props():
    wm = bpy.context.window_manager
    wm["tpp_automergeuv"] = 0


# remove ID-properties from window-manager
def remove_props():
    wm = bpy.context.window_manager
    if "tpp_automergeuv" in wm:
        del wm["tpp_automergeuv"]
    if "tpp_toolmode_time" in wm:
        del wm["tpp_toolmode_time"]
    if "tpp_toolmode_brushloc" in wm:
        del wm["tpp_toolmode_brusloc"]


# calculate new snapped location based on start point (sx,sy)
# and current mouse point (mx,my).  These coords appear to be
# in 2D screen coords, with the origin at:
# bottom-left, +x right, +y up.

# =>?
def do_snap( sx, sy, mx, my ):
    # compute delta between current mouse position and
    # start position
    dx = mx - sx
    dy = my - sy
    adx = abs(dx)
    ady = abs(dy)

    # if delta is "close enough" to the diagonal
    if abs( ady - adx ) < 0.5 * max(adx, ady):

        # use a simple algorithm to snap based on horizontal
        # distance (could use vertical distance, or could use
        # radial distance but that would require more calcs).
        if (dx > 0 and dy > 0) or (dx < 0 and dy < 0):
            x = mx
            y = sy + dx
        elif (dx > 0 and dy < 0) or (dx < 0 and dy > 0):
            x = mx
            y = sy - dx
        else:
            x = mx
            y = my
    elif ( adx > ady ):
        # closer to y-axis, snap vertical
        x = mx
        y = sy
    else:
        # closer to x-axis, snap horizontal
        x = sx
        y = my

    return (x, y)




##########################################
#                                        #
# Classes   =>?                          #
#                                        #
##########################################

#  =>?
class ImageBuffer:
    # based on script by Domino from BlenderArtists
    # licensed GPL v2 or later
    def __init__(self, image):
        self.image = image
        self.x, self.y = self.image.size
        self.buffer = list(self.image.pixels)

    def update(self):
        self.image.pixels = self.buffer

    def _index(self, x, y):
        if x < 0 or y < 0 or x >= self.x or y >= self.y:
            return None
        return (x + y * self.x) * 4

    def set_pixel(self, x, y, colour):
        index = self._index(x, y)
        if index is not None:
            index = int(index)
            self.buffer[index:index + 4] = colour

    def get_pixel(self, x, y):
        index = self._index(x, y)
        if index is not None:
            index = int(index)
            return self.buffer[index:index + 4]
        else:
            return None


# 2d bin packing  =>?
class PackTree(object):
    # based on python recipe by S W on ActiveState
    # PSF license, 16 oct 2005. (GPL compatible)
    def __init__(self, area):
        if len(area) == 2:
            area = (0,0,area[0],area[1])
        self.area = area

    def get_width(self):
        return self.area[2] - self.area[0]
    width = property(fget=get_width)

    def get_height(self):
        return self.area[3] - self.area[1]
    height = property(fget=get_height)

    def insert(self, area):
        if hasattr(self, 'child'):
            a = self.child[0].insert(area)
            if a is None:
                return self.child[1].insert(area)
            else:
                return a

        area = PackTree(area)
        if area.width <= self.width and area.height <= self.height:
            self.child = [None,None]
            self.child[0] = PackTree((self.area[0]+area.width, self.area[1], self.area[2], self.area[1] + area.height))
            self.child[1] = PackTree((self.area[0], self.area[1]+area.height, self.area[2], self.area[3]))
            return PackTree((self.area[0], self.area[1], self.area[0]+area.width, self.area[1]+area.height))


##########################################
#                                        #
# Class Operators                        #
#                                        #
##########################################

class AddDefaultImage(Operator):
    '''Create and assign a new default image to the object'''
    bl_idname = "object.add_default_image"
    bl_label = "Add default image"

    @classmethod
    def poll(cls, context):
        return(context.active_object and context.active_object.type=='MESH')

    def invoke(self, context, event):
        ob = context.active_object
        mat = bpy.data.materials.new("default")

        #Add texture to the mat
        tex = bpy.data.textures.new("default", 'IMAGE')
        img = bpy.data.images.new("default", 1024, 1024, alpha=True)
        ts = mat.texture_slots.add()
        tex.image = img
        ts.texture = tex

        ob.data.materials.append(mat)
        return {'FINISHED'}


class AutoMergeUV(Operator):
    '''Have UV Merge enabled by default for merge actions'''
    bl_idname = "paint.auto_merge_uv"
    bl_label = "AutoMerge UV"


    def invoke(self, context, event):
        wm = context.window_manager
        if "tpp_automergeuv" not in wm:
            init_props()
        wm["tpp_automergeuv"] = 1 - wm["tpp_automergeuv"]

        km = bpy.context.window_manager.keyconfigs.default.keymaps['Mesh']
        for kmi in km.keymap_items:
            if kmi.idname == "mesh.merge":
                kmi.properties.uvs = wm["tpp_automergeuv"]

        return {'FINISHED'}


class MakeBrushImageTexture(Operator):        #class command
    bl_label = "New Texture from Image"
    bl_idname = "gizmo.image_texture"

    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self,context):
        tex = bpy.data.textures.new("ImageTexture",'NONE')
        tex.use_nodes = True
        remove = tex.node_tree.nodes[1]
        tex.node_tree.nodes.remove(remove)
        tex.node_tree.nodes.new("TextureNodeImage")
        tex.node_tree.links.new(tex.node_tree.nodes[0].inputs[0],tex.node_tree.nodes[1].outputs[0])
        i = bpy.data.images.load(self.filepath)
        tex.node_tree.nodes[1].image = i
        bpy.context.tool_settings.image_paint.brush.texture = tex

        tex.node_tree.nodes[1].location = [0,50]
        tex.node_tree.nodes[0].location = [200,50]

        if bpy.context.mode == 'SCULPT':
            bpy.context.tool_settings.sculpt.brush.texture = tex
        elif bpy.context.mode == 'PAINT_VERTEX':
            bpy.context.tool_settings.vertex_paint.brush.texture = tex
        #elif bpy.context.mode == 'PAINT_WEIGHT':
        #   bpy.context.tool_settings.weight_paint.brush.texture = tex
        elif bpy.context.mode == 'PAINT_TEXTURE':
            bpy.context.tool_settings.image_paint.brush.texture = tex

        return set()


class MakeBrushImageTextureMask(Operator):    #class command
    bl_label = "New Mask Texture from Image"
    bl_idname = "gizmo.image_texture_mask"

    filepath = bpy.props.StringProperty(subtype="FILE_PATH")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self,context):
        tex = bpy.data.textures.new("ImageTextureMask",'NONE')
        tex.use_nodes = True
        remove = tex.node_tree.nodes[1]
        tex.node_tree.nodes.remove(remove)
        tex.node_tree.nodes.new("TextureNodeImage")
        tex.node_tree.nodes.new("TextureNodeRGBToBW")


        tex.node_tree.links.new(tex.node_tree.nodes[0].inputs[0],tex.node_tree.nodes[2].outputs[0])
        tex.node_tree.links.new(tex.node_tree.nodes[2].inputs[0],tex.node_tree.nodes[1].outputs[0])
        tex.node_tree.nodes[1].location = [0,50]
        tex.node_tree.nodes[2].location = [200,50]
        tex.node_tree.nodes[0].location = [400,50]


        i = bpy.data.images.load(self.filepath)
        tex.node_tree.nodes[1].image = i
        #if bpy.context.mode == 'SCULPT':
        #   bpy.context.tool_settings.sculpt.brush.mask_texture = tex
        #elif bpy.context.mode == 'PAINT_VERTEX':
        #   bpy.context.tool_settings.vertex_paint.brush.mask_texture = tex
        #elif bpy.context.mode == 'PAINT_WEIGHT':
        #   bpy.context.tool_settings.weight_paint.brush.mask_texture = tex
        if bpy.context.mode == 'PAINT_TEXTURE':
            bpy.context.tool_settings.image_paint.brush.mask_texture = tex
        return set()


class BrushPopup(Operator):
    bl_idname = "view3d.brush_popup"
    bl_label = "Brush settings"
    bl_options = {'REGISTER', 'UNDO'}


    @staticmethod
    def paint_settings(context):
        toolsettings = context.tool_settings

        if context.vertex_paint_object:
            return toolsettings.vertex_paint
        elif context.weight_paint_object:
            return toolsettings.weight_paint
        elif context.image_paint_object:
            if (toolsettings.image_paint and toolsettings.image_paint.detect_data()):
                return toolsettings.image_paint

            return None
        return None

    @staticmethod
    def unified_paint_settings(parent, context):
        ups = context.tool_settings.unified_paint_settings
        parent.label(text="Unified Settings:")
        row = parent.row()
        row.prop(ups, "use_unified_size", text="Size")
        row.prop(ups, "use_unified_strength", text="Strength")
        if context.weight_paint_object:
            parent.prop(ups, "use_unified_weight", text="Weight")
        elif context.vertex_paint_object or context.image_paint_object:
            parent.prop(ups, "use_unified_color", text="Color")
        else:
            parent.prop(ups, "use_unified_color", text="Color")

    @staticmethod
    def prop_unified_size(parent, context, brush, prop_name, icon='NONE', text="", slider=False):
        ups = context.tool_settings.unified_paint_settings
        ptr = ups if ups.use_unified_size else brush
        parent.prop(ptr, prop_name, icon=icon, text=text, slider=slider)

    @staticmethod
    def prop_unified_strength(parent, context, brush, prop_name, icon='NONE', text="", slider=False):
        ups = context.tool_settings.unified_paint_settings
        ptr = ups if ups.use_unified_strength else brush
        parent.prop(ptr, prop_name, icon=icon, text=text, slider=slider)

    @staticmethod
    def prop_unified_weight(parent, context, brush, prop_name, icon='NONE', text="", slider=False):
        ups = context.tool_settings.unified_paint_settings
        ptr = ups if ups.use_unified_weight else brush
        parent.prop(ptr, prop_name, icon=icon, text=text, slider=slider)

    @staticmethod
    def prop_unified_color(parent, context, brush, prop_name, text=""):
        ups = context.tool_settings.unified_paint_settings
        ptr = ups if ups.use_unified_color else brush
        parent.prop(ptr, prop_name, text=text)

    @staticmethod
    def prop_unified_color_picker(parent, context, brush, prop_name, value_slider=True):
        ups = context.tool_settings.unified_paint_settings
        ptr = ups if ups.use_unified_color else brush
        parent.template_color_picker(ptr, prop_name, value_slider=value_slider)


    def check(self, context):
        '''
        settings = self.paint_settings(context)
        brush_updated = settings.brush.is_updated
        if brush_updated:
            return True
        '''
        return True


    @classmethod
    def poll(self, context):
        obj =  context.active_object
        if obj is not None:
            A = context.active_object.type == 'MESH'
            B = context.mode in {'PAINT_TEXTURE','PAINT_VERTEX','PAINT_WEIGHT'}
            return A and B


    def brush_texpaint_common(self, layout, context, brush, settings, projpaint=False):
        capabilities = brush.image_paint_capabilities

        col = layout.column()

        if brush.image_tool in {'DRAW', 'FILL'}:
            if brush.blend not in {'ERASE_ALPHA', 'ADD_ALPHA'}:
                if not brush.use_gradient:
                    self.prop_unified_color_picker(col, context, brush, "color", value_slider=True)

                if settings.palette:
                    col.template_palette(settings, "palette", color=True)

                if brush.use_gradient:
                    col.label("Gradient Colors")
                    col.template_color_ramp(brush, "gradient", expand=True)

                    if brush.image_tool != 'FILL':
                        col.label("Background Color")
                        row = col.row(align=True)
                        self.prop_unified_color(row, context, brush, "secondary_color", text="")

                    if brush.image_tool == 'DRAW':
                        col.prop(brush, "gradient_stroke_mode", text="Mode")
                        if brush.gradient_stroke_mode in {'SPACING_REPEAT', 'SPACING_CLAMP'}:
                            col.prop(brush, "grad_spacing")
                    elif brush.image_tool == 'FILL':
                        col.prop(brush, "gradient_fill_mode")
                else:
                    row = col.row(align=True)
                    self.prop_unified_color(row, context, brush, "color", text="")
                    if brush.image_tool == 'FILL' and not projpaint:
                        col.prop(brush, "fill_threshold")
                    else:
                        self.prop_unified_color(row, context, brush, "secondary_color", text="")
                        row.separator()
                        row.operator("paint.brush_colors_flip", icon='FILE_REFRESH', text="")

        elif brush.image_tool == 'SOFTEN':
            col = layout.column(align=True)
            col.row().prop(brush, "direction", expand=True)
            col.separator()
            col.prop(brush, "sharp_threshold")
            if not projpaint:
                col.prop(brush, "blur_kernel_radius")
            col.separator()
            col.prop(brush, "blur_mode")
        elif brush.image_tool == 'MASK':
            col.prop(brush, "weight", text="Mask Value", slider=True)

        elif brush.image_tool == 'CLONE':
            col.separator()
            if projpaint:
                if settings.mode == 'MATERIAL':
                    col.prop(settings, "use_clone_layer", text="Clone from paint slot")
                elif settings.mode == 'IMAGE':
                    col.prop(settings, "use_clone_layer", text="Clone from image/UV map")

                if settings.use_clone_layer:
                    ob = context.active_object
                    col = layout.column()

                    if settings.mode == 'MATERIAL':
                        if len(ob.material_slots) > 1:
                            col.label("Materials")
                            col.template_list("MATERIAL_UL_matslots", "",
                                              ob, "material_slots",
                                              ob, "active_material_index", rows=2)

                        mat = ob.active_material
                        if mat:
                            col.label("Source Clone Slot")
                            col.template_list("TEXTURE_UL_texpaintslots", "",
                                              mat, "texture_paint_images",
                                              mat, "paint_clone_slot", rows=2)

                    elif settings.mode == 'IMAGE':
                        mesh = ob.data

                        clone_text = mesh.uv_texture_clone.name if mesh.uv_texture_clone else ""
                        col.label("Source Clone Image")
                        col.template_ID(settings, "clone_image")
                        col.label("Source Clone UV Map")
                        col.menu("VIEW3D_MT_tools_projectpaint_clone", text=clone_text, translate=False)
            else:
                col.prop(brush, "clone_image", text="Image")
                col.prop(brush, "clone_alpha", text="Alpha")

        col.separator()

        if capabilities.has_radius:
            row = col.row(align=True)
            self.prop_unified_size(row, context, brush, "size", slider=True, text="Radius")
            self.prop_unified_size(row, context, brush, "use_pressure_size")

        row = col.row(align=True)

        if capabilities.has_space_attenuation:
            row.prop(brush, "use_space_attenuation", toggle=True, icon_only=True)

        self.prop_unified_strength(row, context, brush, "strength", text="Strength")
        self.prop_unified_strength(row, context, brush, "use_pressure_strength")

        if brush.image_tool in {'DRAW', 'FILL'}:
            col.separator()
            col.prop(brush, "blend", text="Blend")

        col = layout.column()

        # use_accumulate
        if capabilities.has_accumulate:
            col = layout.column(align=True)
            col.prop(brush, "use_accumulate")

        if projpaint:
            col.prop(brush, "use_alpha")

        col.prop(brush, "use_gradient")

        col.separator()
        col.template_ID(settings, "palette", new="palette.new")


    def draw(self, context):
        # Init values
        toolsettings = context.tool_settings
        settings = self.paint_settings(context)
        brush = settings.brush
        ipaint = toolsettings.image_paint

        layout = self.layout

        # Stroke mode
        col = layout.column()
        col.prop(brush, "stroke_method", text="")

        if brush.use_anchor:
            col.separator()
            col.prop(brush, "use_edge_to_edge", "Edge To Edge")

        if brush.use_airbrush:
            col.separator()
            col.prop(brush, "rate", text="Rate", slider=True)

        if brush.use_space:
            col.separator()
            row = col.row(align=True)
            row.prop(brush, "spacing", text="Spacing")
            row.prop(brush, "use_pressure_spacing", toggle=True, text="")

        if brush.use_line or brush.use_curve:
            col.separator()
            row = col.row(align=True)
            row.prop(brush, "spacing", text="Spacing")

        if brush.use_curve:
            col.separator()
            col.template_ID(brush, "paint_curve", new="paintcurve.new")
            col.operator("paintcurve.draw")

        else:
            col.separator()

            row = col.row(align=True)
            row.prop(brush, "use_relative_jitter", icon_only=True)
            if brush.use_relative_jitter:
                row.prop(brush, "jitter", slider=True)
            else:
                row.prop(brush, "jitter_absolute")
            row.prop(brush, "use_pressure_jitter", toggle=True, text="")

            col = layout.column()
            col.separator()

            if brush.brush_capabilities.has_smooth_stroke:
                col.prop(brush, "use_smooth_stroke")

                sub = col.column()
                sub.active = brush.use_smooth_stroke
                sub.prop(brush, "smooth_stroke_radius", text="Radius", slider=True)
                sub.prop(brush, "smooth_stroke_factor", text="Factor", slider=True)

        layout.prop(settings, "input_samples")

        # Curve stroke
        col = layout.column(align=True)
         
        settings = self.paint_settings(context)
 
        brush = settings.brush
 
        layout.template_curve_mapping(brush, "curve", brush=True)
 
        col = layout.column(align=True)
        row = col.row(align=True)
        row.operator("brush.curve_preset", icon='SMOOTHCURVE', text="").shape = 'SMOOTH'
        row.operator("brush.curve_preset", icon='SPHERECURVE', text="").shape = 'ROUND'
        row.operator("brush.curve_preset", icon='ROOTCURVE', text="").shape = 'ROOT'
        row.operator("brush.curve_preset", icon='SHARPCURVE', text="").shape = 'SHARP'
        row.operator("brush.curve_preset", icon='LINCURVE', text="").shape = 'LINE'
        row.operator("brush.curve_preset", icon='NOCURVE', text="").shape = 'MAX'


        # Symetries mode
        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(ipaint, "use_symmetry_x", text="X", toggle=True)
        row.prop(ipaint, "use_symmetry_y", text="Y", toggle=True)
        row.prop(ipaint, "use_symmetry_z", text="Z", toggle=True)

        # imagepaint tool operate buttons
        col = layout.split().column()
        col.template_ID_preview(settings, "brush", new="brush.add", rows=3, cols=8)

        ########################################################################
        # Texture Paint Mode #

        if context.image_paint_object and brush:
            self.brush_texpaint_common( layout, context, brush, settings, True)

        ########################################################################
        # Weight Paint Mode #
        elif context.weight_paint_object and brush:

            col = layout.column()

            row = col.row(align=True)
            self.prop_unified_weight(row, context, brush, "weight", slider=True, text="Weight")

            row = col.row(align=True)
            self.prop_unified_size(row, context, brush, "size", slider=True, text="Radius")
            self.prop_unified_size(row, context, brush, "use_pressure_size")

            row = col.row(align=True)
            self.prop_unified_strength(row, context, brush, "strength", text="Strength")
            self.prop_unified_strength(row, context, brush, "use_pressure_strength")

            col.prop(brush, "vertex_tool", text="Blend")

            if brush.vertex_tool == 'BLUR':
                col.prop(brush, "use_accumulate")
                col.separator()

            col = layout.column()
            col.prop(toolsettings, "use_auto_normalize", text="Auto Normalize")
            col.prop(toolsettings, "use_multipaint", text="Multi-Paint")

        ########################################################################
        # Vertex Paint Mode #
        elif context.vertex_paint_object and brush:
            col = layout.column()
            self.prop_unified_color_picker(col, context, brush, "color", value_slider=True)
            if settings.palette:
                col.template_palette(settings, "palette", color=True)
            self.prop_unified_color(col, context, brush, "color", text="")

            col.separator()
            row = col.row(align=True)
            self.prop_unified_size(row, context, brush, "size", slider=True, text="Radius")
            self.prop_unified_size(row, context, brush, "use_pressure_size")

            row = col.row(align=True)
            self.prop_unified_strength(row, context, brush, "strength", text="Strength")
            self.prop_unified_strength(row, context, brush, "use_pressure_strength")

            col.separator()
            col.prop(brush, "vertex_tool", text="Blend")

            col.separator()
            col.template_ID(settings, "palette", new="palette.new")



    def invoke(self, context, event):
        if context.space_data.type == 'IMAGE_EDITOR':
            context.space_data.mode = 'PAINT'
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=160)

    def execute(self, context):
        return {'FINISHED'}


class TexturePopup(Operator):
    bl_idname = "view3d.texture_popup"
    bl_label = "Textures and Mask Textures settings"
    bl_options = {'REGISTER', 'UNDO'}

    toggleMenu = bpy.props.BoolProperty(default=True)  # toogle texture or Mask menu

    def check(self, context):
        return True

    @classmethod
    def poll(self, context):
        obj =  context.active_object
        if obj is not None:
            A = obj.type == 'MESH'
            B = context.mode == 'PAINT_TEXTURE'
            return A and B

    def draw(self, context):
        # Init values
        toolsettings = context.tool_settings
        brush = toolsettings.image_paint.brush
        tex_slot = brush.texture_slot
        mask_tex_slot = brush.mask_texture_slot

        unified = toolsettings.unified_paint_settings
        settings = toolsettings.image_paint

        # textures panel
        layout = self.layout

        # Parameter Toggle Menu
        _TITLE = 'TEXTURES' if self.toggleMenu else 'MASKS'
        _ICON = 'TEXTURE' if self.toggleMenu else 'MOD_MASK'
        Menu = layout.row()
        Menu.prop(self, "toggleMenu", text=_TITLE, icon=_ICON)


        if self.toggleMenu:
            col = layout.column()                                   #TEXTURES
            col.template_ID_preview(brush, "texture", new="texture.new", \
                                                                rows=3, cols=8)
            layout.label(text="Brush Mapping:")

            # texture_map_mode
            layout.row().prop(tex_slot, "tex_paint_map_mode", text="")
            layout.separator()

            if tex_slot.map_mode == 'STENCIL':
                if brush.texture and brush.texture.type == 'IMAGE':
                    layout.operator("brush.stencil_fit_image_aspect")
                layout.operator("brush.stencil_reset_transform")

            # angle and texture_angle_source
            if tex_slot.has_texture_angle:
                col = layout.column()
                col.label(text="Angle:")
                col.prop(tex_slot, "angle", text="")
                if tex_slot.has_texture_angle_source:
                    col.prop(tex_slot, "use_rake", text="Rake")

                    if brush.brush_capabilities.has_random_texture_angle and tex_slot.has_random_texture_angle:
                        col.prop(tex_slot, "use_random", text="Random")
                        if tex_slot.use_random:
                            col.prop(tex_slot, "random_angle", text="")


            # scale and offset
            split = layout.split()
            split.prop(tex_slot, "offset")
            split.prop(tex_slot, "scale")

            row = layout.row()
            row.operator(MakeBrushImageTexture.bl_idname)
        else:
            col = layout.column()                                 #MASK TEXTURE
            col.template_ID_preview(brush, "mask_texture", new="texture.new", \
                                                                rows=3, cols=8)
            layout.label(text="Mask Mapping:")
            # map_mode
            layout.row().prop(mask_tex_slot, "mask_map_mode", text="")
            layout.separator()

            if mask_tex_slot.map_mode == 'STENCIL':
                if brush.mask_texture and brush.mask_texture.type == 'IMAGE':
                    layout.operator("brush.stencil_fit_image_aspect").mask = True
                layout.operator("brush.stencil_reset_transform").mask = True

            col = layout.column()
            col.prop(brush, "use_pressure_masking", text="")
            # angle and texture_angle_source
            if mask_tex_slot.has_texture_angle:
                col = layout.column()
                col.label(text="Angle:")
                col.prop(mask_tex_slot, "angle", text="")
                if mask_tex_slot.has_texture_angle_source:
                    col.prop(mask_tex_slot, "use_rake", text="Rake")

                    if brush.brush_capabilities.has_random_texture_angle and mask_tex_slot.has_random_texture_angle:
                        col.prop(mask_tex_slot, "use_random", text="Random")
                        if mask_tex_slot.use_random:
                            col.prop(mask_tex_slot, "random_angle", text="")

            # scale and offset
            split = layout.split()
            split.prop(mask_tex_slot, "offset")
            split.prop(mask_tex_slot, "scale")
            row = layout.row()
            row.operator(MakeBrushImageTextureMask.bl_idname)


    def invoke(self, context, event):
        if context.space_data.type == 'IMAGE_EDITOR':
            context.space_data.mode = 'PAINT'
        return context.window_manager.\
                                invoke_props_dialog(self, width=160)

    def execute(self, context):
        return {'FINISHED'}

class SelectVertgroup(bpy.types.Operator):
    """Select Vertgroup"""
    bl_idname = "object.select_vgroup"


    bl_label = "Select VGroup"
    bl_options = { 'REGISTER', 'UNDO' }

    def execute(self, context):

        bpy.ops.object.editmode_toggle()#toggle editmode
        bpy.ops.object.vertex_group_select()#select current active vgroup
        bpy.ops.object.editmode_toggle()#toggle editmode
        bpy.ops.paint.texture_paint_toggle()#Texpaint
        bpy.context.object.data.use_paint_mask = True #set face select masking on in case we forgot


        return {'FINISHED'}

class DeselectVertgroup(bpy.types.Operator):
    """Deselect Vertgroup"""
    bl_idname = "object.deselect_vgroup"


    bl_label = "Deselect VGroup"
    bl_options = { 'REGISTER', 'UNDO' }

    def execute(self, context):

        bpy.ops.object.editmode_toggle()#toggle editmode
        bpy.ops.object.vertex_group_deselect()#select current active vgroup
        bpy.ops.object.editmode_toggle()#toggle editmode
        bpy.ops.paint.texture_paint_toggle()#Texpaint
        bpy.context.object.data.use_paint_mask = True #set face select masking on in case we forgot


        return {'FINISHED'}

class Slots_projectpaint(Operator):
    bl_idname = "slots.projectpaint"
    bl_label = "Slots & VGroups"
    bl_options = {'REGISTER', 'UNDO'}

    def check(self, context):
        return True

    @classmethod
    def poll(cls, context):
        brush = context.tool_settings.image_paint.brush
        ob = context.active_object
        if (brush is not None and ob is not None):
            A = context.active_object.type == 'MESH'
            B = context.mode == 'PAINT_TEXTURE'
            return A and B

    def draw(self, context):
        settings = context.tool_settings.image_paint
        ob = context.active_object
        layout = self.layout
        col = layout.column()

        col.separator()
        col.operator("image.save_dirty", text="Save All Images")

        layout = self.layout

        ob = context.object
        group = ob.vertex_groups.active

        rows = 2
        if group:
            rows = 4

        row = layout.row()
        row.template_list("MESH_UL_vgroups", "", ob, "vertex_groups", ob.vertex_groups, "active_index", rows=rows)

        col = row.column(align=True)
        col.operator("object.vertex_group_add", icon='ZOOMIN', text="")
        col.operator("object.vertex_group_remove", icon='ZOOMOUT', text="").all = False
        col.menu("MESH_MT_vertex_group_specials", icon='DOWNARROW_HLT', text="")


        if group:
            col.separator()
            col.operator("object.vertex_group_move", icon='TRIA_UP', text="").direction = 'UP'
            col.operator("object.vertex_group_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

        if ob.vertex_groups and (ob.mode == 'EDIT' or (ob.mode == 'WEIGHT_PAINT' and ob.type == 'MESH' and ob.data.use_paint_mask_vertex)):
            row = layout.row()

            sub = row.row(align=True)
            sub.operator("object.vertex_group_assign", text="Assign")
            sub.operator("object.vertex_group_remove_from", text="Remove")

            sub = row.row(align=True)
            sub.operator("object.vertex_group_select", text="Select")
            sub.operator("object.vertex_group_deselect", text="Deselect")


        layout.prop(context.tool_settings, "vertex_group_weight", text="Weight")

        #row = layout.row()
        row = layout.row(align=True)
        row.operator("object.select_vgroup", text = "Select VGroup", icon = 'ROTACTIVE')
        #row = layout.column()
        row.operator("object.deselect_vgroup", text = "Deselect VGroup", icon = 'ROTACTIVE')

        layout = self.layout
        col = layout.column()

        col.label("Painting Mode")
        col.prop(settings, "mode", text="")
        col.separator()

        if settings.mode == 'MATERIAL':
            if len(ob.material_slots) > 1:
                col.label("Materials")
                col.template_list("MATERIAL_UL_matslots", "layers",
                                  ob, "material_slots",
                                  ob, "active_material_index", rows=2)

            mat = ob.active_material
            if mat:
                col.label("Available Paint Slots")
                col.template_list("TEXTURE_UL_texpaintslots", "",
                                  mat, "texture_paint_images",
                                  mat, "paint_active_slot", rows=2)

                if mat.texture_paint_slots:
                    slot = mat.texture_paint_slots[mat.paint_active_slot]
                else:
                    slot = None

                if (not mat.use_nodes) and context.scene.render.engine in {'BLENDER_RENDER', 'BLENDER_GAME'}:
                    row = col.row(align=True)
                    row.operator_menu_enum("paint.add_texture_paint_slot", "type")
                    row.operator("paint.delete_texture_paint_slot", text="", icon='X')

                    if slot:
                        col.prop(mat.texture_slots[slot.index], "blend_type")
                        col.separator()

                if slot and slot.index != -1:
                    col.label("UV Map")
                    col.prop_search(slot, "uv_layer", ob.data, "uv_textures", text="")

        elif settings.mode == 'IMAGE':
            mesh = ob.data
            uv_text = mesh.uv_textures.active.name if mesh.uv_textures.active else ""
            col.label("Canvas Image")
            col.template_ID(settings, "canvas")
            col.operator("image.new", text="New").gen_context = 'PAINT_CANVAS'
            col.label("UV Map")
            col.menu("VIEW3D_MT_tools_projectpaint_uvlayer", text=uv_text, translate=False)


    def invoke(self, context,event):
        if context.space_data.type == 'IMAGE_EDITOR':
            context.space_data.mode = 'PAINT'
        return context.window_manager.invoke_props_dialog(self, width=240)

    def execute(self, context):
        return {'FINISHED'}


class ChangeSelection(Operator):
    '''Select more or less vertices/edges/faces, connected to the original selection'''
    bl_idname = "paint.change_selection"
    bl_label = "Change selection"

    mode = bpy.props.EnumProperty(name="Mode",
        items = (("more", "More", "Select more vertices/edges/faces"),
            ("less", "Less", "Select less vertices/edges/faces")),
        description = "Choose whether the selection should be increased or decreased",
        default = 'more')

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        bpy.ops.object.mode_set(mode='EDIT')
        if self.mode == 'more':
            bpy.ops.mesh.select_more()
        else: #self.mode == 'less'
            bpy.ops.mesh.select_less()
        bpy.ops.object.mode_set(mode='TEXTURE_PAINT')

        return {'FINISHED'}


class DefaultMaterial(Operator):
    '''Add a default dif/spec/normal material to an object'''
    bl_idname = "object.default_material"
    bl_label = "Default material"

    @classmethod
    def poll(cls, context):
        object = context.active_object
        if not object or not object.data:
            return False
        return object.type == 'MESH'

    def invoke(self, context, event):
        objects = context.selected_objects
        for ob in objects:
            if not ob.data or ob.type != 'MESH':
                continue

        mat = bpy.data.materials.new(ob.name)

        # diffuse texture
        tex = bpy.data.textures.new(ob.name+"_DIFF", 'IMAGE')
        ts = mat.texture_slots.add()
        ts.texture_coords = 'UV'
        ts.texture = tex
        # specular texture
        tex = bpy.data.textures.new(ob.name+"_SPEC", 'IMAGE')
        ts = mat.texture_slots.add()
        ts.texture_coords = 'UV'
        ts.use_map_color_diffuse = False
        ts.use_map_specular = True
        ts.texture = tex
        # normal texture
        tex = bpy.data.textures.new(ob.name+"_NORM", 'IMAGE')
        tex.use_normal_map = True
        ts = mat.texture_slots.add()
        ts.texture_coords = 'UV'
        ts.use_map_color_diffuse = False
        ts.use_map_normal = True
        ts.texture = tex

        ob.data.materials.append(mat)

        return {'FINISHED'}


class GridTexture(Operator):
    '''Toggle between current texture and UV / Colour grids'''
    bl_idname = "paint.grid_texture"
    bl_label = "Grid texture"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        Egne = bpy.context.scene.render.engine
        if Egne == 'BLENDER_RENDER':
            objects = bpy.context.selected_objects
            meshes = [object.data for object in objects if object.type == 'MESH']
            if not meshes:
                self.report({'INFO'}, "Couldn't locate meshes to operate on")
                return {'CANCELLED'}

            tex_image = []
            for mesh in meshes:
                for mat in mesh.materials:
                    for tex in [ts.texture for ts in mat.texture_slots if ts and ts.texture.type=='IMAGE' and ts.texture.image]:
                        tex_image.append([tex.name, tex.image.name])
            if not tex_image:
                self.report({'INFO'}, "Couldn't locate textures to operate on")
                return {'CANCELLED'}

            first_image = bpy.data.images[tex_image[0][1]]
            if "grid_texture_mode" in first_image:
                mode = first_image["grid_texture_mode"]
            else:
                mode = 1

            if mode == 1:
                # original textures, change to new UV grid
                width = max([bpy.data.images[image].size[0] for tex, image in tex_image])
                height = max([bpy.data.images[image].size[1] for tex, image in tex_image])
                new_image = bpy.data.images.new("temp_grid", width=width, height=height)
                new_image.generated_type = 'UV_GRID'
                new_image["grid_texture"] = tex_image
                new_image["grid_texture_mode"] = 2
                for tex, image in tex_image:
                    bpy.data.textures[tex].image = new_image
            elif mode == 2:
                # change from UV grid to Colour grid
                first_image.generated_type = 'COLOR_GRID'
                first_image["grid_texture_mode"] = 3
            elif mode == 3:
                # change from Colour grid back to original textures
                if "grid_texture" not in first_image:
                    first_image["grid_texture_mode"] = 1
                    self.report({'ERROR'}, "Couldn't retrieve original images")
                    return {'FINISHED'}
                tex_image = first_image["grid_texture"]
                for tex, image in tex_image:
                    if tex in bpy.data.textures and image in bpy.data.images:
                        bpy.data.textures[tex].image = bpy.data.images[image]
                bpy.data.images.remove(first_image)

            return {'FINISHED'}
        elif Egne =='CYCLES':

            return {'FINISHED'}
        else:
            return {'FINISHED'}


class MassLinkAppend(Operator, ImportHelper):
    '''Import objects from multiple blend-files at the same time'''
    bl_idname = "wm.mass_link_append"
    bl_label = "Mass Link/Append"
    bl_options = {'REGISTER', 'UNDO'}

    active_layer = bpy.props.BoolProperty(name="Active Layer",
        default=True,
        description="Put the linked objects on the active layer")
    autoselect = bpy.props.BoolProperty(name="Select",
        default=True,
        description="Select the linked objects")
    instance_groups = bpy.props.BoolProperty(name="Instance Groups",
        default=False,
        description="Create instances for each group as a DupliGroup")
    link = bpy.props.BoolProperty(name="Link",
        default=False,
        description="Link the objects or datablocks rather than appending")
    relative_path = bpy.props.BoolProperty(name="Relative Path",
        default=True,
        description="Select the file relative to the blend file")

    def execute(self, context):
        directory, filename = os.path.split(bpy.path.abspath(self.filepath))
        files = []

        # find all blend-files in the given directory
        for root, dirs, filenames in os.walk(directory):
            for file in filenames:
                if file.endswith(".blend"):
                    files.append([root+os.sep, file])
            break # don't search in subdirectories

        # append / link objects
        old_selection = context.selected_objects
        new_selection = []
        print("_______ Texture Paint Plus _______")
        print("You can safely ignore the line(s) below")
        for directory, filename in files:
            # get object names
            with bpy.data.libraries.load(directory + filename) as (append_lib, current_lib):
                ob_names = append_lib.objects
            for name in ob_names:
                append_libs = [{"name":name} for name in ob_names]
            # appending / linking
            bpy.ops.wm.link_append(filepath=os.sep+filename+os.sep+"Object"+os.sep,
                filename=name, directory=directory+filename+os.sep+"Object"+os.sep,
                link=self.link, autoselect=True, active_layer=self.active_layer,
                relative_path=self.relative_path, instance_groups=self.instance_groups,
                files=append_libs)
            if not self.link:
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.make_local()
                bpy.ops.object.make_local(type='SELECTED_OBJECTS_DATA')
            new_selection += context.selected_objects
        print("__________________________________")
        bpy.ops.object.select_all(action='DESELECT')
        if self.autoselect:
            for ob in new_selection:
                ob.select = True
        else:
            for ob in old_selection:
                ob.select = True

        return {'FINISHED'}


class ReloadImage(Operator):      #unused class?
    '''Reload image displayed in image-editor'''
    bl_idname = "paint.reload_image"
    bl_label = "Reload image"

    def invoke(self, context, event):
        images = get_images_in_editors(context)
        for img in images:
            img.reload()

        # make the changes immediately visible in 3d-views
        # image editor updating is handled in get_images_in_editors()
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()

        return{'FINISHED'}


class ReloadImages(Operator):
    '''Reload all images'''
    bl_idname = "paint.reload_images"
    bl_label = "Reload all images"

    def invoke(self, context, event):
        reloaded = [0, 0]
        for img in bpy.data.images:
            img.reload()

        # make the changes immediately visible in image editors and 3d-views
        for area in context.screen.areas:
            if area.type == 'IMAGE_EDITOR' or area.type == 'VIEW_3D':
                area.tag_redraw()

        return {'FINISHED'}


class SampleColor(Operator):
    '''Sample color'''
    bl_idname = "paint.sample_color_custom"
    bl_label = "Sample color"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        mesh = context.active_object.data
        paint_mask = mesh.use_paint_mask
        mesh.use_paint_mask = False
        bpy.ops.paint.sample_color('INVOKE_REGION_WIN')
        mesh.use_paint_mask = paint_mask

        return {'FINISHED'}


class SaveImage(Operator):
    '''Save image displayed in image-editor'''
    bl_idname = "paint.save_image"
    bl_label = "Save image"

    def invoke(self, context, event):
        images = get_images_in_editors(context)
        for img in images:
            img.save()

        return{'FINISHED'}


class SaveImages(Operator):
    '''Save all images'''
    bl_idname = "wm.save_images"
    bl_label = "Save all images"

    def invoke(self, context, event):
        correct = 0
        for img in bpy.data.images:
            try:
                img.save()
                correct += 1
            except:
                # some images don't have a source path (e.g. render result)
                pass

        self.report({'INFO'}, "Saved " + str(correct) + " images")

        return {'FINISHED'}


class SyncSelection(Operator):
    '''Sync selection from uv-editor to 3d-view'''
    bl_idname = "uv.sync_selection"
    bl_label = "Sync selection"

    _timer = None
    _selection_3d = []
    handle1 = None
    handle2 = None
    handle3 = None
    area = None
    region = None
    overlay_vertices = []
    overlay_edges = []
    overlay_faces = []
    position_vertices = []
    position_edges = []
    position_faces = []
    position2_vertices = []
    position2_edges = []
    position2_edges = []

    @classmethod
    def poll(cls, context):
        return(context.active_object and context.active_object.mode=='EDIT')

    def modal(self, context, event):
        if self.area:
            self.area.tag_redraw()
        if context.area:
            context.area.tag_redraw()

        if context.window_manager.tpp.sync_enabled == -1:
            self.region.callback_remove(self.handle1)
            self.region.callback_remove(self.handle2)
            context.region.callback_remove(self.handle3)
            self.area = None
            self.region = None
            context.window_manager.tpp.sync_enabled = 0
            return {"CANCELLED"}

        return {'PASS_THROUGH'}

    def invoke(self, context, event):
        if context.window_manager.tpp.sync_enabled < 1:
            for area in context.screen.areas:
                if area.type == 'VIEW_3D':
                    self.area = area
                    for region in area.regions:
                        if region.type == 'WINDOW':
                            self.region = region
                            context.window_manager.tpp.sync_enabled = 1

                            # getting overlay selection
                            old_sync = context.tool_settings.use_uv_select_sync
                            old_select_mode = [x for x in context.tool_settings.mesh_select_mode]
                            context.tool_settings.mesh_select_mode = [True, False, False]
                            bpy.ops.object.mode_set(mode='OBJECT')
                            mesh = context.active_object.data
                            self._selection_3d = [v.index for v in mesh.vertices if v.select]
                            tfl = mesh.uv_textures.active
                            selected = []
                            for mface, tface in zip(mesh.faces, tfl.data):
                                selected += [mface.vertices[i] for i, x in enumerate(tface.select_uv) if x]
                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.mesh.select_all(action='DESELECT')
                            bpy.ops.object.mode_set(mode='OBJECT')
                            context.tool_settings.use_uv_select_sync = True
                            for v in selected:
                                mesh.vertices[v].select = True

                            bpy.ops.object.mode_set(mode='EDIT')
                            bpy.ops.object.mode_set(mode='OBJECT')

                            # indices for overlay in 3d-view
                            self.overlay_vertices = [vertex.index for vertex in mesh.vertices if vertex.select]
                            self.overlay_edges = [edge.index for edge in mesh.edges if edge.select]
                            self.overlay_faces = [face.index for face in mesh.faces if face.select]

                            # overlay positions for image editor
                            dict_vertex_pos = dict([[i, []] for i in range(len(mesh.vertices))])
                            tfl = mesh.uv_textures.active
                            for mface, tface in zip(mesh.faces, tfl.data):
                                for i, vert in enumerate(mface.vertices):
                                    dict_vertex_pos[vert].append([co for co in tface.uv[i]])

                            self.position2_vertices = []
                            for v in self.overlay_vertices:
                                for pos in dict_vertex_pos[v]:
                                    self.position2_vertices.append(pos)

                            # set everything back to original state
                            bpy.ops.object.mode_set(mode='EDIT')
                            context.tool_settings.use_uv_select_sync = old_sync
                            bpy.ops.mesh.select_all(action='DESELECT')
                            bpy.ops.object.mode_set(mode='OBJECT')
                            for v in self._selection_3d:
                                mesh.vertices[v].select = True
                            bpy.ops.object.mode_set(mode='EDIT')
                            context.tool_settings.mesh_select_mode = old_select_mode


                            # 3d view callbacks
                            context.window_manager.modal_handler_add(self)
                            self.handle1 = region.callback_add(sync_calc_callback,
                                (self, context, area, region), "POST_VIEW")
                            self.handle2 = region.callback_add(sync_draw_callback,
                                (self, context), "POST_PIXEL")

                            # image editor callback
                            self.handle3 = context.region.callback_add(sync_draw_callback2,
                                (self, context), "POST_VIEW")

                            break
                    break
        else:
            context.window_manager.tpp.sync_enabled = -1

        return {'RUNNING_MODAL'}


class ToggleAddMultiply(Operator):
    '''Toggle between Add and Multiply blend modes'''
    bl_idname = "paint.toggle_add_multiply"
    bl_label = "Toggle add/multiply"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        brush = context.tool_settings.image_paint.brush
        if brush.blend != 'ADD':
            brush.blend = 'ADD'
        else:
            brush.blend = 'MUL'

        return {'FINISHED'}


class ToggleColorSoftLightScreen(Operator):
    '''Toggle between Color and Softlight and Screen blend modes'''
    bl_idname = "paint.toggle_color_soft_light_screen"
    bl_label = "Toggle color-softlight-screen"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        brush = context.tool_settings.image_paint.brush
        if brush.blend != 'COLOR' and brush.blend != 'SOFTLIGHT':
            brush.blend = 'COLOR'
        elif brush.blend == 'COLOR':
            brush.blend = 'SOFTLIGHT'
        elif brush.blend == 'SOFTLIGHT':
            brush.blend = 'SCREEN'

        return {'FINISHED'}


class ToggleAlphaMode(Operator):
    '''Toggle between Add Alpha and Erase Alpha blend modes'''
    bl_idname = "paint.toggle_alpha_mode"
    bl_label = "Toggle alpha mode"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        brush = context.tool_settings.image_paint.brush
        if brush.blend != 'ERASE_ALPHA':
            brush.blend = 'ERASE_ALPHA'
        else:
            brush.blend = 'ADD_ALPHA'

        return {'FINISHED'}


class ToggleImagePaint(bpy.types.Operator):
    '''Toggle image painting in the UV/Image editor'''
    bl_idname = "paint.toggle_image_paint"
    bl_label = "Image Painting"

    @classmethod
    def poll(cls, context):
        return(context.space_data.type == 'IMAGE_EDITOR')

    def invoke(self, context, event):
        if (context.space_data.mode == 'VIEW'):
            context.space_data.mode = 'PAINT'
        elif (context.space_data.mode == 'PAINT'):
            context.space_data.mode = 'MASK'
        elif (context.space_data.mode == 'MASK'):
            context.space_data.mode = 'VIEW'

        return {'FINISHED'}


class InitPaintBlend(bpy.types.Operator):
    '''Toggle between Add Alpha and Erase Alpha blend modes'''
    bl_idname = "paint.init_blend_mode"
    bl_label = "Init paint blend mode"

    @classmethod
    def poll(cls, context):
        return bpy.ops.paint.image_paint.poll()

    def invoke(self, context, event):
        brush = context.tool_settings.image_paint.brush
        brush.blend = 'MIX'

        return {'FINISHED'}


class ToggleUVSelectSync(Operator):
    '''Toggle use_uv_select_sync in the UV editor'''
    bl_idname = "uv.toggle_uv_select_sync"
    bl_label = "UV Select Sync"

    @classmethod
    def poll(cls, context):
        return(context.space_data.type == 'IMAGE_EDITOR')

    def invoke(self, context, event):
        context.tool_settings.use_uv_select_sync = not context.tool_settings.use_uv_select_sync

        return {'FINISHED'}



##########################################
#                                        #
# User Properties                        #
#                                        #
##########################################

# property group containing all properties of the add-on
class TexturePaintPlusProps(bpy.types.PropertyGroup):

    sync_enabled = bpy.props.IntProperty(name = "Enabled",
                                        description = "internal use",
                                        default = 0)

    toolmode_enabled = bpy.props.IntProperty(name = "Enabled",
                                            description = "internal use",
                                            default = 0)

    toolmode_mode = bpy.props.StringProperty(name = "Mode",
                                            description = "internal use",
                                            default = "")

    toolmode_tool = bpy.props.StringProperty(name = "Tool",
                                            description = "internal use",
                                            default = "")

    line_last = bpy.props.BoolProperty(name = "Last_f",
                                       description = "Last position valid",
                                       default = False)

    line_x = bpy.props.IntProperty(name = "Last_x",
                                   description = "Last position X",
                                   default = 0)

    line_y = bpy.props.IntProperty(name = "Last_y",
                                   description = "Last position y",
                                   default = 0)



#legend:
#(--) =  No shortcut!
classes =   [AddDefaultImage,                #add defauft paint image (Shift ALt X) 3DVIEW
            AutoMergeUV,                    #add "autofusion UVs" in >> UI>Mesh menu [EDIT MODE] (--)
            MakeBrushImageTexture,          #add a paint texture (--)
            MakeBrushImageTextureMask,      #add a mask paint texture (--)

            BrushPopup,                     #brush panel (W) PAINT
            TexturePopup,                   #textures et mask panel (Alt W) PAINT
            Slots_projectpaint,             #images slots panel (Shift W) PAINT
            ChangeSelection,                #multi-selections in UI Blender (--)

            DefaultMaterial,                #add a default material (Ctrl Alt X) 3DVIEW
            GridTexture,                    #show an UV grid texture (G) PAINT
            MassLinkAppend,                 #add several images folder (Ctrl F1) WINDOW
            ReloadImage,                    #reload active paint image [unused?] ========================
            ReloadImages,                   #reload all paint images (Ctrl Alt R) WINDOW
            SampleColor,                    #color sample tool (OS clic droit) PAINT
            SaveImage,                      #save paint image (ALt S) PAINT
            SaveImages,                     #save all paint images (Ctrl Alt S) WINDOW
            SyncSelection,                  #[unused?] 3DVIEW-EDIT  =======================
            ToggleUVSelectSync,             #[unused?] IMAGE_EDITOR =======================
            ToggleAddMultiply,              #Toggle Add/Multiply paint mode (D) PAINT
            ToggleColorSoftLightScreen,     #Toggle Color*softlight paint mode (shift D) PAINT
            ToggleAlphaMode,                #Toggle AddAlpha/EraseAlpha paint mode (A) PAINT
            ToggleImagePaint,               #Cyclic image/paint/mask  mode (B) IMAGE_EDITOR
            InitPaintBlend,                 #Reinit mix paint mode (Alt D) PAINT
            SelectVertgroup,                #Select active vertex group in Texture Paint mode
            DeselectVertgroup,              #Deselect active vertex group in Texture paint mode
            TexturePaintPlusProps]          #toutes les variables de l'addon




def menu_func(self, context):               #Add to UI>Mesh menu [EDIT MODE] => checkbox "Automerge uv"
    layout = self.layout
    wm = context.window_manager

    AME = "tpp_automergeuv"  in wm
    Icon = 'CHECKBOX_HLT' if AME else 'CHECKBOX_DEHLT'
    layout.operator("paint.auto_merge_uv", icon = Icon)


def menu_mesh_select_mode(self, context):   #Add to Selection mode Menu (ctrl Tab) [EDIT MODE] => multi-selections
    layout = self.layout
    layout.separator()

    prop = layout.operator("wm.context_set_value", text="Vertex + Edge", icon='EDITMODE_HLT')
    prop.value = "(True, True, False)"
    prop.data_path = "tool_settings.mesh_select_mode"

    prop = layout.operator("wm.context_set_value", text="Vertex + Face", icon='ORTHO')
    prop.value = "(True, False, True)"
    prop.data_path = "tool_settings.mesh_select_mode"

    prop = layout.operator("wm.context_set_value", text="Edge + Face", icon='SNAP_FACE')
    prop.value = "(False, True, True)"
    prop.data_path = "tool_settings.mesh_select_mode"

    layout.separator()

    prop = layout.operator("wm.context_set_value", text="All", icon='OBJECT_DATAMODE')
    prop.value = "(True, True, True)"
    prop.data_path = "tool_settings.mesh_select_mode"


def menu_snap(self, context):               #Add to Snap menu (Shift S)[OBJECT MODE]  => object origins changes
    layout = self.layout
    layout.separator()
    layout.operator("object.origin_set", text="Geometry to Origin")
    layout.operator("object.origin_set", text="Origin to Geometry").type = 'ORIGIN_GEOMETRY'
    layout.operator("object.origin_set", text="Origin to 3D Cursor").type = 'ORIGIN_CURSOR'


def register():
    import bpy
    # register classes
    init_props()
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.tpp = bpy.props.PointerProperty(\
                                                type = TexturePaintPlusProps)

    # add ImagePaint keymap entries
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Image Paint']
    kmi = km.keymap_items.new("paint.toggle_alpha_mode", 'A', 'PRESS') #ok
    kmi = km.keymap_items.new("wm.context_toggle", 'B', 'PRESS')
    kmi.properties.data_path = "user_preferences.system.use_mipmaps"
    kmi = km.keymap_items.new("paint.toggle_add_multiply", 'D', 'PRESS')#ok
    kmi = km.keymap_items.new("paint.toggle_color_soft_light_screen", 'D', 'PRESS', shift=True)#ok
    kmi = km.keymap_items.new("paint.init_blend_mode", 'D', 'PRESS', alt=True)#ok
    kmi = km.keymap_items.new("paint.sample_color_custom", 'RIGHTMOUSE', 'PRESS', oskey=True)
    kmi = km.keymap_items.new("paint.grid_texture", 'G', 'PRESS')
    kmi = km.keymap_items.new("paint.save_image", 'S', 'PRESS', alt=True) #?
    kmi = km.keymap_items.new("view3d.brush_popup", 'W', 'PRESS')#ok
    kmi = km.keymap_items.new("view3d.texture_popup", 'W', 'PRESS', alt=True)#ok
    kmi = km.keymap_items.new("slots.projectpaint", 'W', 'PRESS', shift=True)#ok

    # add 3DView keymap entries
    km = bpy.context.window_manager.keyconfigs.default.keymaps['3D View']
    kmi = km.keymap_items.new("object.default_material", 'X', 'PRESS', alt=True, ctrl=True)
    kmi = km.keymap_items.new("object.add_default_image", 'X', 'PRESS', shift=True, alt=True) #ok object.add_default_image

    # deactivate to prevent clashing------------------------------------
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Window']
    for kmi in km.keymap_items:
        if kmi.type == 'S' and not kmi.any and not kmi.shift and kmi.ctrl and kmi.alt and not kmi.oskey:
            kmi.active = False

    # add Window keymap entry
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Window']
    kmi = km.keymap_items.new("wm.mass_link_append", 'F1', 'PRESS', ctrl=True)#ok
    kmi = km.keymap_items.new("paint.reload_images", 'R', 'PRESS', alt=True, ctrl=True)#ok
    kmi = km.keymap_items.new("image.save_dirty", 'S','PRESS', alt=True, ctrl=True)#ok


    # deactivate and remap to prevent clashing -------------------------
    if bpy.context.user_preferences.inputs.select_mouse == 'RIGHT':
        right_mouse = ['RIGHTMOUSE', 'SELECTIONMOUSE']
    else: #'LEFT'
        right_mouse = ['RIGHTMOUSE', 'ACTIONMOUSE']
    km = bpy.context.window_manager.keyconfigs.default.keymaps['3D View']
    for kmi in km.keymap_items:
        if kmi.type in right_mouse and kmi.alt and not kmi.ctrl and not kmi.shift:
            # deactivate
            kmi.active = False
    for kmi in km.keymap_items:
        if kmi.type in right_mouse and not kmi.alt and not kmi.ctrl and not kmi.shift:
            # remap
            kmi.alt = True

    # add menu entries
    bpy.types.VIEW3D_MT_edit_mesh.prepend(menu_func)
    bpy.types.VIEW3D_MT_edit_mesh_select_mode.append(menu_mesh_select_mode)
    bpy.types.VIEW3D_MT_snap.append(menu_snap)


def unregister():
    # menu entries
    bpy.types.VIEW3D_MT_snap.remove(menu_snap)
    bpy.types.VIEW3D_MT_edit_mesh_select_mode.remove(menu_mesh_select_mode)
    bpy.types.VIEW3D_MT_edit_mesh.remove(menu_func)

    # ImagePaint keymap entries
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Image Paint']
    for kmi in km.keymap_items:
        if kmi.idname in ["view3d.brush_popup", "view3d.texture_popup", "paint.toggle_alpha_mode",  "paint.sample_color_custom",
        "paint.toggle_add_multiply", "paint.toggle_color_soft_light_screen", "paint.init_blend_mode", "paint.grid_texture", "paint.reload_image", "paint.save_image"]:
            km.keymap_items.remove(kmi)
        elif kmi.idname == "wm.context_toggle":
            if getattr(kmi.properties, "data_path", False) in [ "active_object.show_wire", "user_preferences.system.use_mipmaps"]:
                km.keymap_items.remove(kmi)
        elif kmi.idname == "wm.context_set_enum":
            if getattr(kmi.properties, "data_path", False) in ["tool_settings.image_paint.brush.blend"]:
                km.keymap_items.remove(kmi)

    # 3DView keymap entry
    km = bpy.context.window_manager.keyconfigs.default.keymaps['3D View']
    for kmi in km.keymap_items:
        if kmi.idname in ["object.add_default_image", "object.default_material"]:
            km.keymap_items.remove(kmi)

    # remap and reactivate original items
    if bpy.context.user_preferences.inputs.select_mouse == 'RIGHT':
        right_mouse = ['RIGHTMOUSE', 'SELECTIONMOUSE']
    else: #'LEFT'
        right_mouse = ['RIGHTMOUSE', 'ACTIONMOUSE']
    km = bpy.context.window_manager.keyconfigs.default.keymaps['3D View']
    for kmi in km.keymap_items:
        if kmi.type in right_mouse and kmi.alt and not kmi.ctrl and not kmi.shift:
            if kmi.active:
                # remap
                kmi.alt = False
            else:
                # reactivate
                kmi.active = True

    # reactive original item
    km = bpy.context.window_manager.keyconfigs.default.keymaps['Window']
    for kmi in km.keymap_items:
        if kmi.type == 'S' and not kmi.any and not kmi.shift and kmi.ctrl and kmi.alt and not kmi.oskey:
            kmi.active = True

    # unregister classes
    remove_props()
    for c in classes:
        bpy.utils.unregister_class(c)
    try:
        del bpy.types.WindowManager.tpp
    except:
        pass

if __name__ == "__main__":
    register()
