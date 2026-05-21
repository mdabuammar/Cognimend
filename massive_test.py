import os
import time
import requests
import json
import sys

UPLOAD_URL = "http://localhost:8001"
QUERY_URL = "http://localhost:8002"

# 5 VERY BIG DOCUMENTS
DOCS = [
    {
        "filename": "apollo_program.txt",
        "title": "History of the Apollo Program",
        "content": """THE APOLLO PROGRAM: A COMPREHENSIVE HISTORY
The Apollo program was the third United States human spaceflight program carried out by the National Aeronautics and Space Administration (NASA), which succeeded in preparing and landing the first humans on the Moon from 1968 to 1972. It was first conceived during Dwight D. Eisenhower's administration as a three-person spacecraft to follow the one-person Project Mercury. Later, Apollo was dedicated to President John F. Kennedy's national goal of "landing a man on the Moon and returning him safely to the Earth" by the end of the 1960s, which he proposed in a May 25, 1961, address to Congress.
The program utilized the Saturn family of expendable launch vehicles. Apollo spacecraft consisted of three parts: a Command Module (CM) with a cabin for the three astronauts, and the only part that returned to Earth; a Service Module (SM), which supported the CM with propulsion, electrical power, oxygen, and water; and a Lunar Module (LM) that had two stages - a descent stage for landing on the Moon, and an ascent stage to place the astronauts back into lunar orbit.
Apollo 11 was the first crewed mission to land on the Moon on July 20, 1969. Commander Neil Armstrong and Lunar Module Pilot Buzz Aldrin formed the American crew that landed the Apollo Lunar Module Eagle. Armstrong became the first person to step onto the lunar surface six hours and 39 minutes later on July 21. Michael Collins drove the Command Module Columbia alone in lunar orbit while they were on the Moon's surface. Armstrong and Aldrin spent 21 hours, 36 minutes on the lunar surface and collected 47.5 pounds (21.5 kg) of lunar material to bring back to Earth.
Tragedy struck the program in 1967 when a cabin fire during a launch rehearsal test at Cape Kennedy launch pad 34 killed all three crew members of Apollo 1: Gus Grissom, Ed White, and Roger Chaffee. This led to a major redesign of the Command Module to address severe safety flaws, including the use of an oxygen-rich atmosphere on the pad and inward-opening hatches that trapped the crew.
The final Apollo mission, Apollo 17, took place in December 1972. Eugene Cernan and Harrison Schmitt spent three days on the lunar surface, conducting extensive geological surveys while Ronald Evans orbited above. The program was officially concluded due to budget cuts and a shift in national priorities toward the Space Shuttle program and low-Earth orbit operations.
"""
    },
    {
        "filename": "quantum_computing.txt",
        "title": "Detailed Guide on Quantum Computing",
        "content": """QUANTUM COMPUTING: PRINCIPLES AND APPLICATIONS
Quantum computing is a rapidly-emerging technology that harnesses the laws of quantum mechanics to solve problems too complex for classical computers. Classical computers, which include smartphones and laptops, encode information in binary "bits" that can either be 0s or 1s. In a quantum computer, the basic unit of memory is a quantum bit or qubit.
Qubits are made using physical systems, such as the spin of an electron or the orientation of a photon. What makes qubits special is their ability to exist in multiple states simultaneously, a phenomenon known as superposition. Thanks to superposition, a quantum computer with several qubits can process a vast number of potential outcomes simultaneously.
Another fundamental principle is quantum entanglement. When qubits become entangled, the state of one qubit instantaneously influences the state of the other, no matter the distance between them. This interconnectedness allows quantum computers to process complex data sets and perform calculations much faster than classical computers because changing the state of an entangled qubit affects its paired counterpart instantly.
Decoherence is the primary challenge in building practical quantum computers. Quantum states are incredibly fragile; any interaction with the external environment, such as a slight temperature fluctuation or a stray magnetic field, can cause the qubit to lose its quantum state and revert to a classical state. This loss of information is known as decoherence. To combat this, most quantum processors must be kept at temperatures near absolute zero (-273.15 degrees Celsius) using specialized dilution refrigerators.
Potential applications of quantum computing are vast. In cryptography, Shor's algorithm running on a sufficiently powerful quantum computer could theoretically break the RSA encryption that secures modern internet communications. In chemistry, quantum computers can accurately simulate molecular interactions at an atomic level, potentially accelerating drug discovery and materials science. Financial institutions are researching quantum algorithms for portfolio optimization and risk analysis, while logistics companies look to quantum computing to solve complex routing and scheduling problems like the Traveling Salesman Problem.
"""
    },
    {
        "filename": "immune_system.txt",
        "title": "Deep Dive into the Human Immune System",
        "content": """THE HUMAN IMMUNE SYSTEM: DEFENDING THE BODY
The human immune system is a complex network of cells, tissues, and organs that work together to defend the body against attacks by "foreign" invaders. These are primarily microbes-tiny organisms such as bacteria, parasites, and fungi that can cause infections. The immune system is incredibly intelligent; it has the ability to distinguish between the body's own cells (self) and foreign cells (non-self).
The immune system is broadly divided into two main categories: the innate immune system and the adaptive immune system. The innate immune system is the body's first line of defense. It is present from birth and provides immediate, non-specific protection. Its components include physical barriers like the skin and mucous membranes, as well as immune cells like macrophages and neutrophils. Macrophages are large white blood cells that swallow and digest microbes and other foreign particles through a process called phagocytosis.
The adaptive immune system, on the other hand, develops over a lifetime of exposure to specific pathogens. It is highly specific and has a "memory." The key players in the adaptive immune system are B cells and T cells, which are types of lymphocytes (white blood cells).
B cells are responsible for producing antibodies. When a B cell encounters a specific antigen (a foreign protein on the surface of a pathogen), it proliferates and transforms into plasma cells, which secrete millions of antibodies. These antibodies lock onto the specific antigen, neutralizing the pathogen or marking it for destruction by other immune cells.
T cells have several functions. Cytotoxic T cells directly attack and destroy infected cells or cancer cells. Helper T cells coordinate the immune response by releasing chemical messengers called cytokines, which stimulate the activity of other immune cells, including B cells and macrophages.
Vaccines leverage the adaptive immune system's memory. By introducing a harmless piece of a pathogen (or a weakened version), a vaccine trains the adaptive immune system to recognize and combat the invader. If the body is later exposed to the actual pathogen, the immune system can mount a rapid and powerful response, preventing severe illness. Autoimmune diseases occur when the immune system mistakenly attacks the body's own healthy cells, leading to conditions such as rheumatoid arthritis, lupus, and type 1 diabetes.
"""
    },
    {
        "filename": "renewable_energy.txt",
        "title": "Comprehensive Overview of Renewable Energy",
        "content": """RENEWABLE ENERGY TECHNOLOGIES AND INTEGRATION
Renewable energy is derived from natural processes that are replenished constantly. In its various forms, it derives directly from the sun, or from heat generated deep within the earth. Included in the definition is electricity and heat generated from solar, wind, ocean, hydropower, biomass, geothermal resources, and biofuels and hydrogen derived from renewable resources.
Solar energy involves capturing the radiant light and heat from the Sun. Photovoltaic (PV) cells convert sunlight directly into electricity using the photoelectric effect. Silicon is the most common semiconductor material used in PV cells. Concentrated solar power (CSP) systems, alternatively, use mirrors or lenses to concentrate a large area of sunlight onto a receiver, converting the solar energy into thermal energy to generate electricity via a steam turbine.
Wind energy relies on airflow through wind turbines to mechanically power generators for electric power. Wind power gives variable power, which is very consistent from year to year but has significant variation over shorter time scales. Therefore, it must be used together with other power sources to give a reliable supply. Offshore wind farms take advantage of stronger, more consistent ocean winds compared to land-based turbines, though they are more expensive to install and maintain.
Hydropower generates electricity by harnessing the energy of falling or flowing water. Large-scale hydroelectric dams are highly efficient but can have massive environmental impacts on river ecosystems. Pumped-storage hydroelectricity acts as a giant battery: during periods of low electrical demand, excess generation capacity is used to pump water into an upper reservoir. When there is high demand, water is released back into the lower reservoir through a turbine, generating electricity.
Geothermal energy taps into the thermal energy generated and stored in the Earth. Geothermal power plants use hydrothermal resources that have both water (hydro) and heat (thermal). These plants require high-temperature hydrothermal resources that come from either dry steam wells or from hot water wells.
The primary challenge of renewable energy integration is intermittency. Because the sun doesn't always shine and the wind doesn't always blow, grid operators must balance supply and demand in real-time. This requires massive advancements in grid-scale energy storage, primarily using lithium-ion battery banks. Additionally, smart grid technologies allow for demand response, where non-critical loads (like water heaters or electric vehicle chargers) are automatically turned off during peak demand periods or when renewable generation drops.
"""
    },
    {
        "filename": "roman_empire.txt",
        "title": "The Architecture of the Roman Empire",
        "content": """ARCHITECTURE AND ENGINEERING OF THE ROMAN EMPIRE
Ancient Roman architecture adopted the external language of classical Greek architecture for the purposes of the ancient Romans, but differed from Greek buildings, becoming a new architectural style. The two styles are often considered one body of classical architecture. Roman architecture flourished in the Roman Republic and even more so under the Empire, when the great majority of surviving buildings were constructed.
The true breakthrough of Roman engineering was the invention of Roman concrete (opus caementicium). Unlike modern concrete, Roman concrete was made from a mixture of volcanic ash (pozzolana), quicklime, and volcanic rock aggregate. This unique chemical composition made it exceptionally durable and allowed it to set even underwater. The use of concrete freed Roman architects from the restrictions of stone and brick, allowing them to construct massive, complex shapes like domes and vaults.
The arch is perhaps the most defining feature of Roman architecture. While the Romans did not invent the arch, they were the first to fully realize its potential for building massive structures above ground. A series of contiguous arches forms a vault, which the Romans used to roof large interior spaces without the need for supporting columns. The cross-vault (or groin vault), formed by the intersection of two barrel vaults, allowed for even larger open spaces and the inclusion of massive windows.
The Colosseum, completed in 80 AD under Emperor Titus, is a masterclass in Roman engineering. The massive amphitheater could hold an estimated 50,000 to 80,000 spectators. Its structural integrity relied heavily on the extensive use of concrete and a complex system of vaulted arches. The building featured a massive retractable awning (the velarium) deployed by sailors to shade spectators from the sun, and an intricate underground network of tunnels and cages (the hypogeum) used to hold gladiators and exotic animals.
Aqueducts demonstrate the Romans' mastery of hydraulic engineering. These massive structures were designed to transport fresh water from distant sources into highly populated cities. The water flowed purely by gravity, requiring a precise and constant downward gradient over tens of miles. The Pont du Gard in France is one of the best-preserved Roman aqueducts, featuring three tiers of arches spanning a river gorge. In Rome itself, the water supplied massive public bathhouses (thermae), private villas, and public fountains.
"""
    }
]

QUERIES = [
    # Apollo
    ("What are the three parts of the Apollo spacecraft?", "Apollo"),
    ("Who died in the Apollo 1 cabin fire?", "Apollo"),
    ("Why was the Apollo program officially concluded?", "Apollo"),
    
    # Quantum
    ("What is decoherence in quantum computing?", "Quantum"),
    ("What does Shor's algorithm do?", "Quantum"),
    ("At what temperature must quantum processors be kept?", "Quantum"),
    
    # Immune
    ("What is the difference between innate and adaptive immunity?", "Immune"),
    ("What do B cells produce?", "Immune"),
    ("What happens during an autoimmune disease?", "Immune"),
    
    # Renewable
    ("How does pumped-storage hydroelectricity work?", "Renewable"),
    ("What is the primary challenge of renewable energy integration?", "Renewable"),
    ("What material is most common in photovoltaic cells?", "Renewable"),
    
    # Rome
    ("What ingredients were used to make Roman concrete?", "Rome"),
    ("What was the hypogeum in the Colosseum used for?", "Rome"),
    ("How did Roman aqueducts transport water?", "Rome")
]

def p(msg): print(msg, flush=True)

def upload_docs():
    p("--- STEP 1: UPLOADING 5 MASSIVE DOCUMENTS ---")
    for doc in DOCS:
        try:
            files = {"file": (doc["filename"], doc["content"].encode(), "text/plain")}
            r = requests.post(f"{UPLOAD_URL}/upload", files=files, data={"title": doc["title"]})
            p(f"Uploaded {doc['filename']}: Status {r.status_code}")
        except Exception as e:
            p(f"Upload failed for {doc['filename']}: {e}")

def run_queries(top_k=3):
    results = []
    for q, topic in QUERIES:
        try:
            r = requests.post(f"{QUERY_URL}/query", json={"question": q, "top_k": top_k})
            if r.ok:
                d = r.json()
                conf = d.get("confidence", 0)
                ans = d.get("answer", "")
                results.append({"query": q, "confidence": conf, "answer": ans, "topic": topic})
            else:
                p(f"Query failed: {r.status_code}")
        except Exception as e:
            p(f"Query error: {e}")
    return results

def rechunk_all():
    try:
        r = requests.post(f"{UPLOAD_URL}/rechunk-all", timeout=120)
        p(f"Rechunking complete: {r.status_code}")
    except Exception as e:
        p(f"Rechunk failed: {e}")

def reindex_all():
    try:
        r = requests.post(f"{UPLOAD_URL}/documents/reindex-all", timeout=120)
        p(f"Reindexing complete: {r.status_code}")
    except Exception as e:
        p(f"Reindex failed: {e}")

def main():
    upload_docs()
    p("Waiting 15 seconds for initial indexing...")
    time.sleep(15)
    
    p("\n--- STEP 2: INITIAL QUERY RUN (top_k=3) ---")
    res1 = run_queries(top_k=3)
    avg_conf1 = sum([r['confidence'] for r in res1]) / len(res1) if res1 else 0
    p(f"Initial Average Confidence: {avg_conf1:.2f}%")
    
    p("\n--- STEP 3: APPLYING FULL SYSTEM PIPELINE AUTO-HEALING ---")
    p("1. Rechunking all documents to optimize context boundaries...")
    rechunk_all()
    time.sleep(5)
    
    p("2. Reindexing all documents in Qdrant Vector DB...")
    reindex_all()
    time.sleep(10)
    
    p("\n--- STEP 4: OPTIMIZED QUERY RUN (top_k=8) ---")
    res2 = run_queries(top_k=8)
    avg_conf2 = sum([r['confidence'] for r in res2]) / len(res2) if res2 else 0
    p(f"Optimized Average Confidence: {avg_conf2:.2f}%")
    
    p("\n--- SAVING REPORT TO ARTIFACT ---")
    artifact_path = "artifacts/massive_pipeline_results.md"
    os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write("# 🌐 Massive Pipeline Test Results\n\n")
        f.write(f"Five large documents covering space, physics, biology, energy, and history were uploaded. A retrieval tuning pipeline was then run before testing 15 queries.\n\n")
        f.write(f"### 📈 Performance Metrics\n")
        f.write(f"- **Initial Average Confidence:** {avg_conf1:.2f}%\n")
        f.write(f"- **Final Optimized Confidence:** {avg_conf2:.2f}%\n\n")
        f.write("### 📝 Query Results\n\n")
        f.write("| Topic | Query | Confidence | Answer |\n")
        f.write("|---|---|---|---|\n")
        for r in res2:
            ans_short = r['answer'].replace("\n", " ")
            f.write(f"| {r['topic']} | {r['query']} | **{r['confidence']}%** | {ans_short} |\n")
            
    p("Finished.")

if __name__ == "__main__":
    main()
