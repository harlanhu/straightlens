% Automatic Lens Distortion Correction Using Two Parameter Polynomial and Division Models with iterative optimization
===============================================

# ABOUT
-------

* Author    : Daniel Santana-Cedrés <dsantana@ctim.es>
              Luis Gómez            <lgomez@ctim.es>
              Miguel Alemán-Flores  <maleman@ctim.es>
              Agustín Salgado       <asalgado@ctim.es>
              Julio Esclarín        <jesclarin@ctim.es>
              Luis Mazorra          <lmazorra@ctim.es>
              Luis Álvarez          <lalvarez@ctim.es>
* Copyright : (C) 2009-2016 IPOL Image Processing On Line http://www.ipol.im/
* License   : CC Creative Commons "Attribution-NonCommercial-ShareAlike" 
              see http://creativecommons.org/licenses/by-nc-sa/3.0/es/deed.en

# OVERVIEW
----------

This source code provides an implementation of a lens distortion correction algorithm 
algorithm as described in IPOL

http://www.ipol.im/pub/art/2016/130/

This program reads an input image and automatically estimates a 2 parameter 
polynomial or division lens distortion model, that it is used to correct image
distortion, after an iterative optimization process. 

The programs produces 4 outputs: 
   (1) The estimated distortion parameters. 
   (2) An output image with the results of Canny Edge Detector.
   (3) An output image with the estimated distorted lines.
   (4) An output image where the distortion model is applied to correct the 
       image distortion. 

# REQUIREMENTS
--------------

The code is written in ANSI C++, and should compile on any system with
an ANSI C compiler.

The libpng header and libraries are required on the system for
compilation and execution. See http://www.libpng.org/pub/png/libpng.html

MacOSX already provides libpng in versions before Montain Lion.
However, if you have problems with png library, you can follow the next steps:
	- Install Hombrew (http://brew.hs) and run the commands:
		* brew doctor
		* brew update
		* brew install libpng
		* brew link libpng --force

# COMPILATION
-------------

We have checked our code on:
	- Fedora 11 (Leonidas) with GCC version 4.4.1-2
	- Ubuntu 14.04 LTS (trusty) with GCC version 4.8.2
	- Windows 7 with Cygwin 6.1 and GCC version 4.8.2
	- MacOSX 10.6.8 (Snow Leopard) Darwin Kernel version 10.8.0 wiht GCC version 4.2.1

Simply use the provided makefile, with the command `make`.
If you want to use the OpenMP library, please use `make OMP=1`.

    g++ -Wall -Wextra -O3 src/main/lens_distortion_correction_2p_iterative_optimization.cpp 

Alternatively, you can manually compile
		src/main/image_contours.cpp src/main/lens_distortion_procedures.cpp 
		src/main/line_extraction.cpp src/auxiliary/ami_lens_distortion_model.cpp 
		src/auxiliary/ami_line_points.cpp src/auxiliary/io_png.cpp src/auxiliary/ami_lens_distortion.cpp 
		src/auxiliary/ami_utilities.cpp src/auxiliary/ami_pol.cpp 
		-lpng -lm -o lens_distortion_correction_2p_iterative_optimization
		
		Or the following alternative compilation line for using the OpenMP library
		
		g++ -Wall -Wextra -O3 -fopenmp src/main/lens_distortion_correction_2p_iterative_optimization.cpp 
    src/main/image_contours.cpp src/main/lens_distortion_procedures.cpp 
    src/main/line_extraction.cpp src/auxiliary/ami_lens_distortion_model.cpp 
    src/auxiliary/ami_line_points.cpp src/auxiliary/io_png.cpp src/auxiliary/ami_lens_distortion.cpp 
    src/auxiliary/ami_utilities.cpp src/auxiliary/ami_pol.cpp 
    -lpng -lm -o lens_distortion_correction_2p_iterative_optimization

# USAGE
-------

This program takes 11 parameters:
“exe_file  input.png output_canny.png output_hough.png output_corrected_image.png high_threshold_Canny initial_distortion_parameter final_distortion_parameter distance_point_line_max_hough angle_point_orientation_max_difference type_of_lens_distortion_model center_optimization primitives_file” 

* 'exe_file ' 		                        : exe file (called ./lens_distortion_correction_2p_iterative_optimization) 
* 'input.png'                             : input image
* 'output_canny.png'                      : output image wiht the detected edges by means of Canny method
* 'output_hough.png'                      : output image with the detected lines by means fof improved Hough transform
* 'output_corrected_image.png'            : output image with the corrected distortion
* 'high_threshold_Canny'                  : float value for the high threshold of the Canny method (between 0.7 and 1.0)
* 'initial_distortion_parameter'          : float value for the initial normalized distortion parameter (greater or equeal to -0.5)
* 'final_distortion_parameter'            : float value for the final normalized distortion parameter (greater or equal to the initial value)
* 'distance_point_line_max_hough'         : maximum distance allowed between points and associated lines
* 'angle_point_orientation_max_difference': maximum difference (in degrees) of the point orientation angle and the line angle
* 'type_of_lens_distortion_model'         : type of the lens distortion model for the correction of the distortion (pol or div)
* 'center_optimization'                   : optimization of the center of the lens distortion model (True or False)
* 'primitives_file'                       : output file for saving information about the detected primitives using the improved Hough transform


# SOURCE CODE ORGANIZATION
--------------------------

The source code is organized in the following folders: 

* 'src/auxiliary': inside this folder there is auxiliar code:
                   - ami_image: class and methods for images.
                   - ami_image_draw: method to draw the detected primitives.
                   - ami_lens_distortion: functions to inverse evaluation of
                     points using a lens distortion model.
                   - ami_lens_distortion_model: class and methods associated to
                     lens distortion models.
                   - ami_line: class and methods for lines.
                   - ami_line_points: class and methods for line points.
                   - ami_point2d: class and methods for 2D points.
                   - ami_pol: polynomial roots computation library.
                   - ami_utilities: some auxiliary macros and functions.
                   - io_png: input/output image library.
                   
* 'src/main':      the main code in which are the algorithms described in the
                   paper:
                   - filters: edge detection.
                   - lens_distortion_correction_2p_iterative_optimization:
                     main program, energy minimization, and iterative 
                     optimization.
                   - lens_distortion_procedures: lens distortion parameters and
                     distortion center estimation, image correction.
                   - line_extraction: improved Hough transform.
                   - image_contours: class to store the edge
                     points, their orientations and its associated methods.
                     Also includes the cleaning process.
                   
* 'documentation': doxygen documentation of the source code.

* 'example'      : example input image and results.


The c++-code files inside the folders "src/main" and "src/auxiliary" will be subjected to 
the IPOL peer-review process.


# EXAMPLE
---------

You can test the program with the provided test image (building.png) in the
following way:

./lens_distortion_correction_2p_iterative_optimization example/building.png example/building_canny.png example/building_hough.png example/building_corrected_image.png 0.8 0.0 3.0 3.0 10.0 div True example/primitives.txt

Furthermore, you can compare your results with the results present inside the folder 'example'



# Thanks
------

The authors would be grateful to recieve any comment, especially about
portability issues, errors, bugs or strange results.



