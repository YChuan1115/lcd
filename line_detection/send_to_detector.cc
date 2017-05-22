// A test function to ask for the detect_line service of the
// line_detection::detector node
#include <line_detection/line_detection.h>

#include <cv_bridge/cv_bridge.h>
#include <image_transport/image_transport.h>
#include <ros/ros.h>
#include <sensor_msgs/Image.h>
#include <sensor_msgs/image_encodings.h>
#include <opencv2/highgui/highgui.hpp>

#include <line_detection/RequestLineDetection.h>

int main(int argc, char** argv) {
  // Do not accept to may arguments.
  if (argc > 3) {
    ROS_INFO(
        "usage: send_image <imagepath> <algorithm> \n"
        "Both arguments may be omitted.");
    return -1;
  }
  // define path for test image
  std::string path;
  if (argc < 2) {
    path =
        "/home/dominik/mydata/polybox/Dokumente/SemesterProject/Code/"
        "kitchen.png";
  } else {
    path = argv[1];
  }
  // Initialie the node.
  ros::init(argc, argv, "send_image");
  ros::NodeHandle node_handle;
  ros::ServiceClient client =
      node_handle.serviceClient<line_detection::RequestLineDetection>(
          "detect_lines");

  // load the test image
  cv::Mat test_image = cv::imread(path, CV_LOAD_IMAGE_COLOR);
  if (!test_image.data) {
    ROS_INFO(
        "The path \"%s\" is not a valid image. Please pass a valid path as "
        "an argument to the function.",
        path.c_str());
    return -1;
  }
  // create service
  line_detection::RequestLineDetection service;
  // write additional information
  std_msgs::Header header;
  header.seq = 1;
  header.stamp = ros::Time::now();
  // Create CvImage
  cv_bridge::CvImage cv_image = cv_bridge::CvImage(
      header, sensor_msgs::image_encodings::RGB8, test_image);
  // Set the service image to the test_image (which is stored in cv_image).
  cv_image.toImageMsg(service.request.image);
  // Set algorithm. Default is LSD.
  if (argc > 2) {
    service.request.detector = atoi(argv[2]);
  } else {
    service.request.detector = 0;
  }
  if (!client.call(service)) {
    ROS_INFO("Call was not succesfull. Check if detector is running.");
  }
  // Paint the lines and display
  cv::Point2i p1, p2;
  cv::Vec3i color = {255, 0, 0};
  cv::Mat display_image = test_image.clone();

  for (int i = 0; i < service.response.start_x.size(); i++) {
    p1.x = service.response.start_x[i];
    p1.y = service.response.start_y[i];
    p2.x = service.response.end_x[i];
    p2.y = service.response.end_y[i];
    cv::line(display_image, p1, p2, color, 2);
  }

  cv::imshow("picture with lines", display_image);
  cv::waitKey(0);
  cv::destroyWindow("picture with lines");

  // This part is to find out in which order the lines are stored.
  int show_num_lines = 1;
  int show_num_times = 10;
  cv::Mat disp_img = test_image.clone();
  for (int i = 0; i < show_num_times; ++i) {
    for (int j = 0; j < show_num_lines; ++j) {
      if (i * show_num_lines + j > service.response.start_x.size()) break;
      p1.x = service.response.start_x[i * show_num_lines + j];
      p1.y = service.response.start_y[i * show_num_lines + j];
      p2.x = service.response.end_x[i * show_num_lines + j];
      p2.y = service.response.end_y[i * show_num_lines + j];
      cv::line(disp_img, p1, p2, color, 2);
    }
    cv::imshow("picture with lines", disp_img);
    cv::waitKey(0);
  }

  return 0;
}
