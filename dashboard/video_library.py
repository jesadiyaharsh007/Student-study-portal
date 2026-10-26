"""The hand-picked lessons behind the Videos page. Every id was checked against YouTube's public
video lookup (oEmbed) when it was added, and the title and channel are YouTube's own.

To add a lesson: find its 11-character id in the YouTube link (watch?v=...), check it opens, and add a line.
"""

# (topic key, label)
TOPICS = (
    ('maths', 'Maths'),
    ('science', 'Science'),
    ('computing', 'Computing'),
    ('statistics', 'Statistics'),
    ('humanities', 'History & economics'),
)

# A talk every student should see first; shown at the top of "All".
FEATURED = ("IlU-zDU6aQ0", 'Marty Lobdell - Study Less Study Smart', 'Pierce College District WA')

# (id, title, channel, topic key)
LESSONS = (
    # Maths
    ('WUvTyaaNkzM', 'The essence of calculus', '3Blue1Brown', 'maths'),
    ('fNk_zzaMoSs', 'Vectors | Chapter 1, Essence of linear algebra', '3Blue1Brown', 'maths'),
    ('kYB8IZa5AuE', 'Linear transformations and matrices | Chapter 3, Essence of linear algebra', '3Blue1Brown', 'maths'),
    ('spUNpyF58BY', 'But what is the Fourier Transform?  A visual introduction.', '3Blue1Brown', 'maths'),
    ('9vKqVkMQHKk', 'The paradox of the derivative | Chapter 2, Essence of calculus', '3Blue1Brown', 'maths'),
    ('S0_qX4VJhMQ', 'Derivative formulas through geometry | Chapter 3, Essence of calculus', '3Blue1Brown', 'maths'),
    ('rAof9Ld5sOg', 'Calculus: Derivatives 1 | Taking derivatives | Differential Calculus | Khan Academy', 'Khan Academy', 'maths'),
    ('NybHckSEQBI', 'Algebra Basics: What Is Algebra? - Math Antics', 'mathantics', 'maths'),
    ('LwCRRUa8yTU', 'College Algebra - Full Course', 'freeCodeCamp.org', 'maths'),
    ('riXcZT2ICjA', 'Introduction to limits | Limits | Differential Calculus | Khan Academy', 'Khan Academy', 'maths'),
    ('WsQQvHm4lSw', 'Understand Calculus in 35 Minutes', 'The Organic Chemistry Tutor', 'maths'),
    ('OmJ-4B-mS-Y', 'The Map of Mathematics', 'Domain of Science', 'maths'),
    # Science
    ('zQGOcOUBi6s', 'The Immune System Explained I – Bacteria Infection', 'Kurzgesagt – In a Nutshell', 'science'),
    ('QOCaacO8wus', 'What Is Life? Is Death Real?', 'Kurzgesagt – In a Nutshell', 'science'),
    ('f-ldPgEfAHI', 'Mitosis: The Amazing Cell Process that Uses Division to Multiply! (Older Video 2016 )', 'Amoeba Sisters', 'science'),
    ('uixA8ZXx0KU', '(OLD VIDEO) Photosynthesis and the Teeny Tiny Pigment Pancakes', 'Amoeba Sisters', 'science'),
    ('FSyAehMdpyI', 'The Nucleus: Crash Course Chemistry #1', 'CrashCourse', 'science'),
    ('QnQe0xW_JY4', 'Carbon... SO SIMPLE: Crash Course Biology #1', 'CrashCourse', 'science'),
    ('kKKM8Y-u7ds', "Newton's Laws: Crash Course Physics #5", 'CrashCourse', 'science'),
    ('e-P5IFTqB98', 'Black Holes Explained –\xa0From Birth to Death', 'Kurzgesagt – In a Nutshell', 'science'),
    ('yWO-cvGETRQ', 'Why Black Holes Could Delete The Universe – The Information Paradox', 'Kurzgesagt – In a Nutshell', 'science'),
    ('JQVmkDUkZT4', 'What Are You?', 'Kurzgesagt – In a Nutshell', 'science'),
    ('Iuv6hY6zsd0', 'The Original Double Slit Experiment', 'Veritasium', 'science'),
    # Computing
    ('rfscVS0vtbw', 'Learn Python - Full Course for Beginners [Tutorial]', 'freeCodeCamp.org', 'computing'),
    ('PkZNo7MFNFg', 'Learn JavaScript - Full Course for Beginners', 'freeCodeCamp.org', 'computing'),
    ('aircAruvnKk', 'But what is a neural network? | Deep learning chapter 1', '3Blue1Brown', 'computing'),
    ('nykOeWgQcHM', '1. What is Computation?', 'MIT OpenCourseWare', 'computing'),
    ('zOjov-2OZ0E', 'Introduction to Programming and Computer Science - Full Course', 'freeCodeCamp.org', 'computing'),
    ('8hly31xKli0', 'Algorithms and Data Structures Tutorial - Full Course for Beginners', 'freeCodeCamp.org', 'computing'),
    ('RBSGKlAvoiM', 'Data Structures Easy to Advanced Course - Full Tutorial from a Google Engineer', 'freeCodeCamp.org', 'computing'),
    ('HXV3zeQKqGY', 'SQL Tutorial - Full Database Course for Beginners', 'freeCodeCamp.org', 'computing'),
    ('kqtD5dpn9C8', 'Python for Beginners - Learn Coding with Python in 1 Hour', 'Programming with Mosh', 'computing'),
    ('eIrMbAQSU34', 'Java Full Course for Beginners', 'Programming with Mosh', 'computing'),
    ('Ilg3gGewQ5U', 'Backpropagation, intuitively | Deep Learning Chapter 3', '3Blue1Brown', 'computing'),
    # Statistics
    ('aFDOzpTeg0s', 'The Essence of Linear Regression!!!', 'StatQuest with Josh Starmer', 'statistics'),
    ('q-BiW5srMFQ', 'How AI works in Super Simple Terms!!!', 'StatQuest with Josh Starmer', 'statistics'),
    ('u_9OA3WRHgo', 'Naive Bayes: Concepts and Code', 'StatQuest with Josh Starmer', 'statistics'),
    ('L3nlGfSyHV0', 'False Discovery Rates, FDR, clearly explained', 'StatQuest with Josh Starmer', 'statistics'),
    ('mIlw5j3WyVk', 'StatQuest: Random Forests Part 2: Missing data and clustering', 'StatQuest with Josh Starmer', 'statistics'),
    ('h5o1n1QMcmM', 'Optimization with Linear Programming (and the Simplex Algorithm), Main Ideas!!!', 'StatQuest with Josh Starmer', 'statistics'),
    ('MXaJ7sa7q-8', 'Introduction to Statistics (1.1)', 'Simple Learning Pro', 'statistics'),
    ('SzZ6GpcfoQY', 'Calculating the Mean, Variance and Standard Deviation, Clearly Explained!!!', 'StatQuest with Josh Starmer', 'statistics'),
    ('nk2CQITm_eo', 'Linear Regression, Clearly Explained!!!', 'StatQuest with Josh Starmer', 'statistics'),
    # History & economics
    ('Yocja_N5s1I', 'The Agricultural Revolution: Crash Course World History #1', 'CrashCourse', 'humanities'),
    ('_XPZQ0LAlR4', 'Archdukes, Cynicism, and World War I: Crash Course World History #36', 'CrashCourse', 'humanities'),
    ('_uk_6vfqwTA', 'WW2 - OverSimplified (Part 1)', 'OverSimplified', 'humanities'),
    ('p7HKvqRI_Bo', 'How does the stock market work? - Oliver Elfenbaum', 'TED-Ed', 'humanities'),
    ('3ez10ADR_gM', 'Intro to Economics: Crash Course Econ #1', 'CrashCourse', 'humanities'),
    ('PHe0bXAIuk0', 'How The Economic Machine Works by Ray Dalio', 'Principles by Ray Dalio', 'humanities'),
    ('d8uTB5XorBw', 'Macroeconomics: Crash Course Economics #5', 'CrashCourse', 'humanities'),
)
