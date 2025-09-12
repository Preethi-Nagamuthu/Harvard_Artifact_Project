# 🏛️ Harvard’s Artifacts Collection: ETL, SQL Analytics & Streamlit Showcase
📌 Project Statement
As an app developer, you are tasked with building an interactive, end-to-end ETL and data exploration platform using the Harvard Art Museums public API. This platform will empower users to dynamically explore, collect, store, and query rich art collections from Harvard’s digital archive — all through a simple, intuitive Streamlit web application.

📝1: Getting the Harvard Art Museums API Key 
Go to: https://www.harvardartmuseums.org/collections/api Scroll down and click on “Send a request”. In the google form, fill in your name, email address, and a brief description of your project or intended use. Submit the form — your API key will be displayed instantly and also sent to your email. The key will look like: “1a7ae53e-......” Use your key to format the following API URLs using params: 

Classification: “https://api.harvardartmuseums.org/classification” 

Details of every classification: “https://api.harvardartmuseums.org/object”

📂 Available Classifications & Data Collection Targets The Harvard Art Museums API offers a rich collection of artifacts categorized under 116 unique classifications — ranging from Paintings, Sculptures, and Coins to Jewelry, Furniture, Drawings, and many more. These classifications represent different types of artworks and historical objects preserved in the museum's digital archive. To-Dos: Collect a minimum of 2500 records for each chosen classification(via streamlit) using the API.

Store these records in 3 separate SQL tables for further querying and analysis.

This ensures broad, diverse data coverage and provides a rich base for meaningful data exploration

# SQL Table creation
🗄️ Table 1: artifact_metadata 

🖼️ Table 2: artifact_media 

🔍 Table 3 : SQL Queries (Display the output in streamlit)

# 📌 📊 Streamlit Application Breakdown
<img width="1898" height="842" alt="image" src="https://github.com/user-attachments/assets/004cc28d-a9e7-45d4-9940-70cef79a5bae" />


