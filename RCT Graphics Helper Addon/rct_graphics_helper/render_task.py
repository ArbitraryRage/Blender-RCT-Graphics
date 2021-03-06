'''
Copyright (c) 2018 RCT Graphics Helper developers

For a complete list of all authors, please refer to the addon's meta info.
Interested in contributing? Visit https://github.com/oli414/Blender-RCT-Graphics

RCT Graphics Helper is licensed under the GNU General Public License version 3.
'''

import bpy
import math
import os
import subprocess

def get_output_path(context, index):
    return bpy.path.abspath(context.scene.rct_graphics_helper_general_properties.output_directory+str(index)+".png")

def get_offset_output_path(context, index):
    return bpy.path.abspath(context.scene.rct_graphics_helper_general_properties.output_directory+str(index)+".txt")

def mask_layer(layer_index, context):
    for render_layer in context.scene.render.layers:
        if render_layer.use:
            for i in range(9): # Maximum of 8 rider pairs, 1 for the vehicle itself
                render_layer.layers[i] = i == layer_index
                render_layer.layers_zmask[i] = i <= layer_index
            render_layer.use_zmask = True
            break

def render(context, index):
    bpy.data.scenes['Scene'].render.filepath = get_output_path(context, index)
    bpy.ops.render.render( write_still = True ) 

def rotate_rig(context, angle, verAngle=0, bankedAngle=0, midAngle=0):
        object = bpy.data.objects['Rig']
        if object is None:
            return False
        object.rotation_euler = (math.radians(bankedAngle),math.radians(verAngle),math.radians(midAngle))
        vJoint = object.children[0] 
        vJoint.rotation_euler = (0,0,math.radians(angle))
        return True

def post_render(context, index):
    magickPath = "magick"
    outputPath = get_output_path(context, index)

    script_file = os.path.realpath(__file__)
    directory = os.path.dirname(script_file)
    palettePath = directory + ("/res/palette.gif" if os.name != 'nt' else "\\res\\palette.gif")
    result = str(subprocess.check_output(magickPath + " " + outputPath + " -fuzz 0 -fill none -opaque \"rgb(57,59,57)\"  -quantize RGB -dither FloydSteinberg -define dither:diffusion-amount=30% -remap \"" + palettePath + "\" -colorspace sRGB -bordercolor none -border 1 -trim -format  \"%[fx:page.width/2 - page.x] %[fx:page.height/2 - page.y]\" -write info: " + outputPath, shell=True))
    
    offset_file = open(get_offset_output_path(context, index), "w")
    offset_file.write(result[2:][:-1])
    offset_file.close()

class AngleSectionTask(object):
    section = None
    frame = None
    frame_index = 0
    sub_index = 0
    out_index = None
    status = "CREATED"
    inverted = False
    context = None
    render_layer = 0

    def __init__(self, section_in, out_index_start, context):
        self.render_layer = section_in.render_layer
        self.inverted = section_in.inverted
        self.section = section_in.angle_section
        self.out_index = out_index_start
        self.frame = None
        self.frame_index = 0
        self.sub_index = 0
        self.status = "CREATED"
        self.context = context

    def step(self):
        if self.frame_index == len(self.section):
            self.status = "FINISHED"
        self.frame = self.section[self.frame_index]

        if self.frame_index == 0:
            mask_layer(self.render_layer, self.context)

        frame = self.frame
        angle = 0
        if frame[0]:
            angle = 45
        angle += 360 / frame[1] * self.sub_index

        extra_roll = 0
        if self.inverted:
            extra_roll = 180

        rotate_rig(self.context, angle, frame[2], frame[3] + extra_roll, frame[4])
        render(self.context, self.out_index)
        post_render(self.context, self.out_index)

        self.out_index += 1
        self.sub_index += 1
        if self.sub_index == self.frame[1]:
            self.sub_index = 0
            self.frame_index += 1
        if self.frame_index == len(self.section):
            self.status = "FINISHED"
            return "FINISHED"
        self.status = "RUNNING"
        return "RUNNING"

class RenderTaskSection(object):
    angle_section = None
    inverted = False
    render_layer = 0
    def __init__(self, angle_section, render_layer = 0, inverted = False):
        self.angle_section = angle_section
        self.inverted = inverted
        self.render_layer = render_layer


class RenderTask(object):
    out_index = 0
    sections = []
    section_index = 0
    status = "CREATED"
    section_task = None
    out_index = 0
    context = None
    def __init__(self, out_index_start, context):
        self.out_index = out_index_start
        self.sections = []
        self.section_index = 0
        self.status = "CREATED"
        self.section_task = None
        self.context = context

    def add(self, angle_section, render_layer = 0, inverted = False):
        self.sections.append(RenderTaskSection(angle_section, render_layer, inverted))

    def step(self):
        if self.section_task is None:
            section = self.sections[self.section_index]
            self.section_task = AngleSectionTask(section, self.out_index, self.context)

        result = self.section_task.step()
        self.out_index = self.section_task.out_index

        if result == "FINISHED":
            self.section_task = None
            self.section_index += 1

            if self.section_index == len(self.sections):
                self.status = "FINISHED"
                return "FINISHED"