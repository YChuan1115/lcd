#!/bin/bash
# NOTE: this is just a test to show that running all the scripts with no
# arguments - therefore letting them read the paths and variables values from
# the config file - should produce the exact same result as when passing the
# argument, e.g., when running the script generate_trajectory_files.sh
source ~/catkin_ws/devel/setup.bash
source ~/catkin_extended_ws/devel/setup.bash
source ~/.virtualenvs/line_tools/bin/activate
CURRENT_DIR=`dirname $0`
source $CURRENT_DIR/config_paths_and_variables.sh

# Check dataset type
if [ -z $DATASET_TYPE ]
then
    echo "Please provide the type of dataset to use. Possible options are 'train' and 'val'. Exiting."
    exit 1
else
    # Check that type is valid
    case "$DATASET_TYPE" in
        train)
            echo "Using training set from pySceneNetRGBD."
            ;;
        val)
            echo "Using validation set from pySceneNetRGBD."
            ;;
        *)
            echo "Invalid argument $DATASET_TYPE. Valid options are 'train' and 'val'. Exiting."
            exit 1
            ;;
    esac
fi

# Check protobuf path
if [ ! -f "$PROTOBUF_PATH" ]
then
    echo "Could not find protobuf file at $PROTOBUF_PATH, exiting."
    exit 1
fi

# Create output trajectories (if nonexistent)
mkdir -p "$BAGFOLDER_PATH"/${DATASET_TYPE};
mkdir -p "$OUTPUTDATA_PATH";
mkdir -p "$TARFILES_PATH"/${DATASET_TYPE};
mkdir -p "$PICKLEANDSPLIT_PATH"/${DATASET_TYPE}/traj_${TRAJ_NUM}/;

# Stop the entire rather than a single command when Ctrl+C
trap "exit" INT

# Generate bag
echo -e "\n****  Generating bag for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
if [ -e "$BAGFOLDER_PATH"/${DATASET_TYPE}/scenenet_traj_${TRAJ_NUM}.bag ]
then
    # PLEASE NOTE! If an error occurs during the formation of the bag (e.g.
    # early termination by interrupt) the script will not check if the bag is
    # valid. Therefore invalid bags should be manually removed.
    echo 'Bag file already existent. Using bag found.';
else
    rosrun scenenet_ros_tools scenenet_to_rosbag.py -scenenet_path "$SCENENET_DATASET_PATH" -trajectory $TRAJ_NUM -output_bag "$BAGFOLDER_PATH"/${DATASET_TYPE}/scenenet_traj_${TRAJ_NUM}.bag -protobuf_path "$PROTOBUF_PATH" -dataset_type ${DATASET_TYPE};
fi

# Create folders to store the data
echo -e "\n**** Creating folders to store the data for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
bash "$CURRENT_DIR"/create_data_dir.sh $TRAJ_NUM "$OUTPUTDATA_PATH" $DATASET_TYPE;
# Only create lines files if not there already (and valid)
if [ -e "$OUTPUTDATA_PATH"/VALID_LINES_FILES_${TRAJ_NUM}_${DATASET_TYPE} ]
then
   echo 'Found valid lines files. Using them.'
else
   # Delete any previous line textfile associated to that trajectory
   rm "$OUTPUTDATA_PATH"/${DATASET_TYPE}_lines/traj_${TRAJ_NUM}/*
   # Play bag and record data

   echo -e "\n**** Playing bag and recording data for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
   roslaunch line_ros_utility detect_cluster_show.launch trajectory:=${TRAJ_NUM} write_path:="$OUTPUTDATA_PATH"/${DATASET_TYPE}_lines/ &
   LAUNCH_PID=$!;
   rosbag play -d 3.5 "$BAGFOLDER_PATH"/${DATASET_TYPE}/scenenet_traj_${TRAJ_NUM}.bag;
   sudo kill ${LAUNCH_PID};

   # Creates a file to say that lines files have been generated, to avoid
   # creating them again if reexecuting the script before moving files
   touch "$OUTPUTDATA_PATH"/VALID_LINES_FILES_${TRAJ_NUM}_${DATASET_TYPE};
fi

# Only generate virtual camera images files if not there already (and valid)
if [ -e "$OUTPUTDATA_PATH"/VALID_VIRTUAL_CAMERA_IMAGES_${TRAJ_NUM}_${DATASET_TYPE} ]
then
   echo 'Found valid virtual camera images. Using them.'
else
   # Generate virtual camera images
   echo -e "\n**** Generating virtual camera images for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
   python "$PYTHONSCRIPTS_PATH"/get_virtual_camera_images.py;
   # Creates a file to say that virtual camera images have been generated, to
   # avoid creating them again if reexecuting the script before moving files
   touch "$OUTPUTDATA_PATH"/VALID_VIRTUAL_CAMERA_IMAGES_${TRAJ_NUM}_${DATASET_TYPE};
fi

# Create archive
echo -e "\n**** Zipping files for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
cd "$OUTPUTDATA_PATH";
tar -cf - ${DATASET_TYPE}/traj_${TRAJ_NUM} ${DATASET_TYPE}_lines/traj_${TRAJ_NUM} | gzip --no-name > "$TARFILES_PATH"/${DATASET_TYPE}/traj_${TRAJ_NUM}.tar.gz

# Split dataset
echo -e "\n**** Splitting dataset for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
python "$PYTHONSCRIPTS_PATH"/split_dataset_with_labels_world.py;
echo -e "\n**** Pickling files for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
python "$PYTHONSCRIPTS_PATH"/pickle_files.py;
for word in test train val all_lines; do
  # NOTE: These files include absolute paths w.r.t to the machine where the
  # data was generated. Still, they are included as a reference to how pickled
  # files were formed (i.e., how data was divided before pickling the data).
  # Further conversion is needed when using these files to train the NN, to
  # replace the absolute path.
  mv "$OUTPUTDATA_PATH"/${word}.txt "$PICKLEANDSPLIT_PATH"/${DATASET_TYPE}/traj_${TRAJ_NUM}/;
done

# Delete lines files and virtual camera images
echo -e "\n**** Delete lines files for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
rm "$OUTPUTDATA_PATH"/VALID_LINES_FILES_${TRAJ_NUM}_${DATASET_TYPE};
rm -r "$OUTPUTDATA_PATH"/${DATASET_TYPE}_lines/traj_${TRAJ_NUM};
echo -e "\n**** Delete virtual camera images for trajectory ${TRAJ_NUM} in ${DATASET_TYPE} set ****\n";
rm "$OUTPUTDATA_PATH"/VALID_VIRTUAL_CAMERA_IMAGES_${TRAJ_NUM}_${DATASET_TYPE};
rm -r "$OUTPUTDATA_PATH"/${DATASET_TYPE}/traj_${TRAJ_NUM};
