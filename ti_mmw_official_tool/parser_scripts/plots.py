import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D

from parser_mmw_demo import parser_one_mmw_demo_output_packet

###############################################################################
# CONFIG
###############################################################################
# capturedFileName = r"C:\Users\c1op3\Downloads\xwr68xx_AOP_processed_stream_2026_02_18T23_40_02_499.dat"

import glob
import os

def find_latest_dat_file(directory_path):
    # Construct the search pattern for .dat files in the specified directory
    search_pattern = os.path.join(directory_path, '*.dat')
    
    # Get a list of all files matching the pattern
    list_of_files = glob.glob(search_pattern)
    
    # Check if any files were found
    if not list_of_files:
        return None # No .dat files found
        
    # Sort the files by their last modification time (os.path.getmtime)
    # The 'key' argument uses a lambda function to get the modification time for each file
    # 'reverse=True' sorts in descending order, putting the latest file first
    latest_file = max(list_of_files, key=os.path.getmtime)
    
    return latest_file


# capturedFileName = r"C:\Users\c1op3\Downloads\xwr68xx_AOP_processed_stream_2026_02_18T23_40_02_499.dat"
your_path = r"C:\Users\c1op3\Downloads"
# If the files are in the current working directory, you can use '.'
# your_path = '.' 

capturedFileName = find_latest_dat_file(your_path)

if capturedFileName:
    print(f"The latest .dat file found is: {capturedFileName}")
else:
    print(f"No .dat files found in the directory: {your_path}")
###############################################################################
# READ FILE
###############################################################################
fp = open(capturedFileName,'rb')
readNumBytes = os.path.getsize(capturedFileName)
print("readNumBytes:", readNumBytes)
allBinData = fp.read()
fp.close()

###############################################################################
# PARSE ALL FRAMES INTO MEMORY
###############################################################################
totalBytesParsed = 0
numFramesParsed = 0

frames_points = []   # list of Nx3 arrays
frames_velocity = [] # list of N arrays

while totalBytesParsed < readNumBytes:

    parser_result, \
    headerStartIndex, \
    totalPacketNumBytes, \
    numDetObj, \
    numTlv, \
    subFrameNumber, \
    detectedX_array, \
    detectedY_array, \
    detectedZ_array, \
    detectedV_array, \
    detectedRange_array, \
    detectedAzimuth_array, \
    detectedElevation_array, \
    detectedSNR_array, \
    detectedNoise_array = parser_one_mmw_demo_output_packet(
        allBinData[totalBytesParsed:], 
        readNumBytes-totalBytesParsed)

    if parser_result != 0:
        break

    totalBytesParsed += (headerStartIndex + totalPacketNumBytes)
    numFramesParsed += 1

    if numDetObj > 0:
        points = np.column_stack((
            detectedX_array[:numDetObj],
            detectedY_array[:numDetObj],
            detectedZ_array[:numDetObj]
        ))
        velocities = np.array(detectedV_array[:numDetObj])

        frames_points.append(points)
        frames_velocity.append(velocities)
    else:
        frames_points.append(np.empty((0,3)))
        frames_velocity.append(np.array([]))

print("Total frames parsed:", numFramesParsed)
###############################################################################
# RANGE VS TIME DATA STRUCTURE
###############################################################################

frame_period = 0.05  # seconds (adjust if you know actual frameCfg)
time_axis = []
range_frames = []

for i, points in enumerate(frames_points):

    current_time = i * frame_period
    time_axis.append(current_time)

    if len(points) > 0:
        ranges = np.sqrt(
            points[:,0]**2 +
            points[:,1]**2 +
            points[:,2]**2
        )
        range_frames.append(ranges)
    else:
        range_frames.append(np.array([]))

time_axis = np.array(time_axis)
###############################################################################
# 3D ANIMATION
###############################################################################
fig = plt.figure()
ax = fig.add_subplot(111, projection='3d')

scatter = ax.scatter([], [], [], c=[], cmap='jet')

ax.set_xlim(-5, 5)
ax.set_ylim(0, 10)
ax.set_zlim(-3, 3)

ax.set_xlabel("X (m)")
ax.set_ylabel("Y (m)")
ax.set_zlabel("Z (m)")
ax.set_title("mmWave Point Cloud Motion")

def update(frame_idx):

    ax.cla()

    points = frames_points[frame_idx]
    velocities = frames_velocity[frame_idx]

    ax.set_xlim(-5, 5)
    ax.set_ylim(0, 10)
    ax.set_zlim(-3, 3)

    ax.set_xlabel("X (m)")
    ax.set_ylabel("Y (m)")
    ax.set_zlabel("Z (m)")
    ax.set_title(f"Frame {frame_idx}")

    if len(points) > 0:
        sc = ax.scatter(
            points[:,0],
            points[:,1],
            points[:,2],
            c=velocities,
            cmap='jet'
        )

    return []

ani = FuncAnimation(
    fig,
    update,
    frames=len(frames_points),
    interval=50
)

plt.show()

###############################################################################
# STATIC RANGE VS TIME PLOT
###############################################################################

plt.figure()

for i in range(len(range_frames)):
    if len(range_frames[i]) > 0:
        t = np.ones(len(range_frames[i])) * time_axis[i]
        plt.scatter(t, range_frames[i], s=5)

plt.xlabel("Time (s)")
plt.ylabel("Range (m)")
plt.title("Range vs Time")
plt.grid()
plt.show()

###############################################################################
# ANIMATED RANGE VS TIME
###############################################################################

fig2, ax2 = plt.subplots()

ax2.set_xlim(0, time_axis[-1])
ax2.set_ylim(0, 10)

ax2.set_xlabel("Time (s)")
ax2.set_ylabel("Range (m)")
ax2.set_title("Range vs Time Animation")

all_times = []
all_ranges = []

def update_range(frame_idx):

    if len(range_frames[frame_idx]) > 0:
        t = np.ones(len(range_frames[frame_idx])) * time_axis[frame_idx]
        all_times.extend(t)
        all_ranges.extend(range_frames[frame_idx])

    ax2.cla()
    ax2.set_xlim(0, time_axis[-1])
    ax2.set_ylim(0, 10)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Range (m)")
    ax2.set_title("Range vs Time Animation")

    ax2.scatter(all_times, all_ranges, s=5)

ani2 = FuncAnimation(
    fig2,
    update_range,
    frames=len(range_frames),
    interval=50
)

plt.show()

#velocity vs time
#