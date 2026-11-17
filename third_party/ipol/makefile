#   Copyright (c) 2010-2014, AMI RESEARCH GROUP <lalvarez@dis.ulpgc.es>
#   License : CC Creative Commons "Attribution-NonCommercial-ShareAlike"
#   see http://creativecommons.org/licenses/by-nc-sa/3.0/es/deed.en


#Use OpenMP with make OMP=1
ifdef OMP
COPT	= -O3 -fopenmp
else
COPT	= -g
endif

CFLAGS	= -Wall -Wextra -std=c++98 $(COPT)
LDFLAGS	+= -lpng -lm

#Flags with LCOV directives
# CFLAGS	= -Wall -Wextra -std=c++98 $(COPT) --coverage
# LDFLAGS	+= -lpng -lm --coverage

AUXILIARY_DIR = src/auxiliary/
MAIN_DIR      = src/main/

lens_distortion_correction_2p_iterative_optimization:\
		lens_distortion_correction_2p_iterative_optimization.o\
		image_contours.o lens_distortion_procedures.o\
		line_extraction.o ami_lens_distortion_model.o ami_line_points.o\
		io_png.o ami_lens_distortion.o ami_pol.o ami_utilities.o
	$(CXX) $(CFLAGS) -o lens_distortion_correction_2p_iterative_optimization\
		lens_distortion_correction_2p_iterative_optimization.o\
		image_contours.o lens_distortion_procedures.o\
		line_extraction.o ami_lens_distortion_model.o\
		ami_line_points.o io_png.o ami_lens_distortion.o ami_pol.o\
		ami_utilities.o $(LDFLAGS)
	
lens_distortion_correction_2p_iterative_optimization.o:\
	$(MAIN_DIR)lens_distortion_correction_2p_iterative_optimization.cpp
	$(CXX) $(CFLAGS) -c $(MAIN_DIR)lens_distortion_correction_2p_iterative_optimization.cpp

image_contours.o: $(MAIN_DIR)image_contours.cpp
	$(CXX) $(CFLAGS) -c $(MAIN_DIR)image_contours.cpp

ami_lens_distortion.o: $(AUXILIARY_DIR)ami_lens_distortion.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)ami_lens_distortion.cpp
	
lens_distortion_procedures.o: $(MAIN_DIR)lens_distortion_procedures.cpp
	$(CXX) $(CFLAGS) -c $(MAIN_DIR)lens_distortion_procedures.cpp

ami_lens_distortion_model.o: $(AUXILIARY_DIR)ami_lens_distortion_model.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)ami_lens_distortion_model.cpp
	
line_extraction.o: $(MAIN_DIR)line_extraction.cpp
	$(CXX) $(CFLAGS) -c $(MAIN_DIR)line_extraction.cpp	
	
io_png.o: $(AUXILIARY_DIR)io_png.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)io_png.cpp

ami_line_points.o: $(AUXILIARY_DIR)ami_line_points.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)ami_line_points.cpp
	
ami_pol.o: $(AUXILIARY_DIR)ami_pol.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)ami_pol.cpp
	
ami_utilities.o: $(AUXILIARY_DIR)ami_utilities.cpp
	$(CXX) $(CFLAGS) -c $(AUXILIARY_DIR)ami_utilities.cpp

.PHONY: clean
clean:
	$(RM) -f *.o lens_distortion_correction_2p_iterative_optimization
	
