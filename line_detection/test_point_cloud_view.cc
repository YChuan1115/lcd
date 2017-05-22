// A test node that computes a point cloud form RGB-D data with the
// line_detection library
#include <line_detection/line_detection.h>

#include <ros/console.h>
#include <ros/ros.h>

#include <pcl/conversions.h>
#include <pcl/visualization/cloud_viewer.h>
#include <pcl/visualization/pcl_visualizer.h>
#include <pcl_ros/point_cloud.h>
#include <pcl_ros/publisher.h>
#include <sensor_msgs/PointCloud2.h>
#include <tf/transform_broadcaster.h>
#include <visualization_msgs/Marker.h>

int main(int argc, char** argv) {
  // This lets DEBUG messages display on console
  if (ros::console::set_logger_level(ROSCONSOLE_DEFAULT_NAME,
                                     ros::console::levels::Debug)) {
    ros::console::notifyLoggerLevelsChanged();
  }
  ros::init(argc, argv, "test_point_cloud");
  ros::NodeHandle node_handle;

  // Load both depth and color image.
  cv::Mat depth;
  cv::Mat image;
  std::string img_path;
  std::string depth_path;
  if (argc == 3) {
    img_path = argv[1];
    depth_path = argv[2];
  } else {
    img_path = "hall.jpg";
    depth_path = "hall_depth.png";
  }
  image = cv::imread("hall.jpg", CV_LOAD_IMAGE_COLOR);
  depth = cv::imread("hall_depth.png", CV_LOAD_IMAGE_UNCHANGED);
  if (!image.data) {
    ROS_INFO_STREAM(
        "Image could not be loaded. Please make shure to run the node in a "
        "directory that contains the image hall.jpg and the corresponding "
        "depth image hall_depth.png."
        << endl
        << "Alternatively give the path of the RGB image as the first argument "
           "and the path of the depth image as the second argument to the "
           "function.");
    return -1;
  }
  if (!depth.data) {
    ROS_INFO_STREAM(
        "Image could not be loaded. Please make sure to run the node in a "
        "directory that contains the image hall.jpg and the corresponding "
        "depth image hall_depth.png"
        << endl
        << "Alternatively give the path of the RGB image as the first argument "
           "and the path of the depth image as the second argument to the "
           "function.");
    return -1;
  }

  // Create a point cloud. The pointer is used to handle to the PCLVsualizer,
  // the reference is needed to handle to cloud to the computePointCloud
  // function.
  pcl::PointCloud<pcl::PointXYZRGB>::Ptr cloud_ptr(
      new pcl::PointCloud<pcl::PointXYZRGB>);
  pcl::PointCloud<pcl::PointXYZRGB>& cloud = *cloud_ptr;

  // Create the calibration matrix. The values are more or less arbitrary.
  cv::Mat K(3, 3, CV_32FC1);
  K.at<float>(0, 0) = 570.3f;
  K.at<float>(0, 1) = 0.0f;
  K.at<float>(0, 2) = 960.0f;
  K.at<float>(1, 0) = 0.0f;
  K.at<float>(1, 1) = 570.3f;
  K.at<float>(1, 2) = 540.0f;
  K.at<float>(2, 0) = 0.0f;
  K.at<float>(2, 1) = 0.0f;
  K.at<float>(2, 2) = 1.0f;

  // Compute the point cloud.
  line_detection::LineDetector line_detector;
  line_detector.computePointCloud(image, depth, K, cloud);

  // // These mean values are used in the unit tests (copied there by hand). So
  // to
  // // make changes there later, this code should stay here.
  // double x_mean = 0;
  // double y_mean = 0;
  // double z_mean = 0;
  // double r_mean = 0;
  // double g_mean = 0;
  // double b_mean = 0;
  // for (int i = 0; i < cloud.size(); i++) {
  //   if (std::isnan(cloud.points[i].x)) continue;
  //   x_mean += cloud.points[i].x;
  //   y_mean += cloud.points[i].y;
  //   z_mean += cloud.points[i].z;
  //   r_mean += cloud.points[i].r;
  //   g_mean += cloud.points[i].g;
  //   b_mean += cloud.points[i].b;
  // }
  // x_mean = x_mean / cloud.size();
  // y_mean = y_mean / cloud.size();
  // z_mean = z_mean / cloud.size();
  // r_mean = r_mean / cloud.size();
  // g_mean = g_mean / cloud.size();
  // b_mean = b_mean / cloud.size();
  // ROS_DEBUG_STREAM("\n"
  //                  << "x_mean = " << x_mean << endl
  //                  << "y_mean = " << y_mean << endl
  //                  << "z_mean = " << z_mean << endl
  //                  << "r_mean = " << r_mean << endl
  //                  << "g_mean = " << g_mean << endl
  //                  << "b_mean = " << b_mean << endl);

  // Sparsify the point cloud for better visualization performance
  pcl::PointCloud<pcl::PointXYZRGB> sparse_cloud;
  for (int i = 0; i < cloud.size(); i += 4) {
    sparse_cloud.push_back(cloud.points[i]);
  }

  // Not to compute the 3D lines, we use a diffetent type of point cloud.
  cv::Mat pc_mat;
  cv::Mat img_gray;
  cvtColor(image, img_gray, CV_BGR2GRAY);
  cv::rgbd::depthTo3d(depth, K, pc_mat);
  std::vector<cv::Vec4f> lines2D;
  std::vector<cv::Vec<float, 6> > lines3D;
  line_detector.detectLines(img_gray, lines2D);
  line_detector.projectLines2Dto3D(lines2D, pc_mat, lines3D);
  // // Visualize it with PCLVisualizer,
  // pcl::visualization::PCLVisualizer viewer("3D Viewer");
  // viewer.setBackgroundColor(1, 1, 1);
  // viewer.addCoordinateSystem(1.0f, "global");
  // viewer.addPointCloud(cloud_ptr, "original point cloud");
  // viewer.spin();

  // Visualize it with RVIZ
  tf::TransformBroadcaster broad_caster;
  tf::Transform transform;
  transform.setOrigin(tf::Vector3(0, 0, 0));
  tf::Quaternion quat;
  quat.setRPY(-3.1415 / 2, 0, 0);
  transform.setRotation(quat);
  ros::Publisher pcl_pub =
      node_handle.advertise<pcl::PointCloud<pcl::PointXYZRGB> >(
          "vis_pointcloud", 2);
  sparse_cloud.header.frame_id = "my_frame";

  ros::Publisher marker_pub = node_handle.advertise<visualization_msgs::Marker>(
      "visualization_marker", 1000);
  visualization_msgs::Marker disp_lines;
  disp_lines.header.frame_id = "my_frame";
  disp_lines.action = visualization_msgs::Marker::ADD;
  disp_lines.type = visualization_msgs::Marker::LINE_LIST;
  disp_lines.scale.x = 0.1;
  disp_lines.color.a = 1;
  disp_lines.color.r = 1;
  disp_lines.color.g = 0;
  disp_lines.color.b = 0;

  geometry_msgs::Point p;
  disp_lines.points.resize(2);

  ros::Rate rate(0.1);
  while (ros::ok()) {
    broad_caster.sendTransform(
        tf::StampedTransform(transform, ros::Time::now(), "map", "my_frame"));
    pcl_pub.publish(sparse_cloud);

    for (size_t i = 0; i < lines3D.size(); ++i) {
      p.x = lines3D[i][0];
      p.y = lines3D[i][1];
      p.z = lines3D[i][2];
      disp_lines.points[0] = p;
      p.x = lines3D[i][3];
      p.y = lines3D[i][4];
      p.z = lines3D[i][5];
      disp_lines.points[1] = p;
      disp_lines.id = i;
      marker_pub.publish(disp_lines);
    }
    rate.sleep();
  }
  return 0;
}
