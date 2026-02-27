from utils_clinica import get_max_follicles, calculate_plates, add_time

print("10/20 -> max:", get_max_follicles("10/20"), "plates:", calculate_plates(get_max_follicles("10/20")))
print("4/5 -> max:", get_max_follicles("4/5"), "plates:", calculate_plates(get_max_follicles("4/5")))
print("24/27 -> max:", get_max_follicles("24/27"), "plates:", calculate_plates(get_max_follicles("24/27")))
print("08:00 +130m ->", add_time("08:00", 130))
