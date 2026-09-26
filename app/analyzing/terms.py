"""Canonical tech-term matching shared by analyze, score, and import.

A term resolves to one canonical key ("golang", "Go" → "go"), so the JD side
and the warehouse side compare like for like. Matching is longest-first with
span masking: "C++20" is claimed before "C++" before "C", "React Native"
before "React", "Node.js" before "JS".
"""

import re

# Canonical display → aliases. Covers common JD asks the user may *not* have,
# so they can show up as missing.
LEXICON: dict[str, list[str]] = {
    # languages
    "Python": [], "Java": [], "JavaScript": ["js", "ecmascript", "es6"],
    "TypeScript": ["ts"], "Go": ["golang"], "Rust": [], "C": [],
    "C++": ["cpp", "c++11", "c++14", "c++17", "c++20", "c++23"],
    "C#": ["csharp", "c sharp"], "Ruby": [], "PHP": [], "Kotlin": [],
    "Swift": [], "Scala": [], "R": [], "MATLAB": [], "Perl": [], "Dart": [],
    "Elixir": [], "Haskell": [], "Julia": [], "Lua": [], "Bash": ["shell scripting"],
    "SQL": [], "HTML": ["html5"], "CSS": ["css3"], "Solidity": [], "Objective-C": [],
    # frontend / mobile
    "React": ["reactjs", "react.js"], "React Native": [], "Next.js": ["nextjs"],
    "Vue": ["vue.js", "vuejs"], "Angular": ["angularjs"], "Svelte": [],
    "Redux": [], "Tailwind CSS": ["tailwind"], "Flutter": [], "Expo": [],
    "SwiftUI": [], "jQuery": [],
    # backend / frameworks
    "Node.js": ["nodejs", "node"], "Express": ["express.js", "expressjs"],
    "Django": [], "Flask": [], "FastAPI": [], "Spring": ["spring boot"],
    "Ruby on Rails": ["rails"], ".NET": ["dotnet", "asp.net"], "GraphQL": [],
    "REST": ["rest api", "rest apis", "restful"], "gRPC": [], "Laravel": [],
    # data / ML
    "pandas": [], "NumPy": [], "scikit-learn": ["sklearn", "scikit learn"],
    "PyTorch": [], "TensorFlow": [], "Keras": [], "OpenCV": [],
    "ONNX Runtime": ["onnx"], "Spark": ["apache spark", "pyspark"],
    "Hadoop": [], "Airflow": ["apache airflow"], "dbt": [], "Kafka": ["apache kafka"],
    "Snowflake": [], "BigQuery": [], "Databricks": [], "Tableau": [],
    "Power BI": ["powerbi"], "Looker": [], "Excel": ["microsoft excel", "ms excel"],
    "LLM": ["llms", "large language models"], "Hugging Face": ["huggingface"],
    "LangChain": [], "machine learning": ["ml"], "deep learning": [],
    "NLP": ["natural language processing"], "computer vision": [],
    "DAX": [], "ETL": [], "data modeling": ["data modelling"],
    # databases
    "PostgreSQL": ["postgres"], "MySQL": [], "SQLite": [], "MongoDB": ["mongo"],
    "Redis": [], "DynamoDB": [], "Cassandra": [], "Elasticsearch": ["elastic search"],
    "Oracle": [], "SQL Server": ["mssql"], "Supabase": [], "Firebase": [],
    # cloud / infra
    "AWS": ["amazon web services"], "Microsoft Azure": ["azure"],
    "GCP": ["google cloud", "google cloud platform"], "Docker": [],
    "Kubernetes": ["k8s"], "Terraform": [], "Ansible": [], "Helm": [],
    "Jenkins": [], "GitHub Actions": [], "CI/CD": ["ci / cd", "continuous integration"],
    "Linux": [], "Nginx": [], "Lambda": ["aws lambda"], "S3": [], "EC2": [],
    "ECS": [], "ECR": [], "CloudFormation": [], "Prometheus": [], "Grafana": [],
    "Datadog": [], "Git": [], "Jira": [], "Figma": [], "microservices": [],
    "WebSockets": ["websocket"], "Azure DevOps": [], "Microsoft Fabric": [],
    "APIs": ["api"], "Agile": [], "UAT": ["user acceptance testing"],
    "version control": [], "Jupyter": ["jupyter notebook", "jupyter notebooks"],
    "SAS": [], "VBA": [], "Informatica": [], "SAP": [],
    # practices / domains that JDs ask for by name
    "data pipelines": ["data pipeline"], "web scraping": ["scraping", "scraper"],
    "prompt engineering": [], "data governance": [], "data quality": [],
    "data migration": ["data migrations"], "data analysis": ["data analytics"],
    "data visualization": ["data visualisation"], "dashboards": ["dashboard"],
    "stakeholder management": [], "statistics": ["statistical analysis"],
    "A/B testing": ["a/b tests", "a/b test"],
}
LEXICON["data modeling"] += ["star schema", "dimensional modeling", "dimensional modelling"]

# Having the left term is evidence of the right ones (a PostgreSQL bullet
# shows SQL). One hop only; used when checking the warehouse, never to
# decide what the JD asked for.
IMPLIES: dict[str, list[str]] = {
    "postgresql": ["sql"], "mysql": ["sql"], "sqlite": ["sql"], "sql server": ["sql"],
    "snowflake": ["sql"], "bigquery": ["sql"], "supabase": ["postgresql", "sql"],
    "pytorch": ["machine learning", "deep learning"], "tensorflow": ["machine learning", "deep learning"],
    "keras": ["machine learning", "deep learning"], "scikit-learn": ["machine learning"],
    "fastapi": ["python", "apis"], "flask": ["python", "apis"], "django": ["python"],
    "pandas": ["python", "data analysis"], "numpy": ["python"],
    "typescript": ["javascript"], "react": ["javascript"], "next.js": ["react", "javascript"],
    "react native": ["react", "javascript"], "node.js": ["javascript"],
    "dax": ["power bi"], "power bi": ["dashboards", "data visualization"],
    "tableau": ["dashboards", "data visualization"], "looker": ["dashboards", "data visualization"],
    "s3": ["aws"], "ecs": ["aws"], "ecr": ["aws"], "ec2": ["aws"], "lambda": ["aws"],
    "git": ["version control"], "graphql": ["apis"], "rest": ["apis"],
    "data quality review": ["data quality"], "stakeholder communication": ["stakeholder management"],
    "database design": ["data modeling"],
}

# Short or common-word names: only match when written with this exact casing,
# and not in the listed non-tech contexts ("go to", "C-suite", "R&D").
_CASE_SENSITIVE = {
    "go": r"Go(?![-\s]+to\b)",
    "c": r"C(?![-&])",
    "r": r"R(?![-&])",
    "swift": r"Swift",
    "spring": r"Spring",
    "express": r"Express",
    "dart": r"Dart",
    "julia": r"Julia",
    "oracle": r"Oracle",
    "rest": r"REST",
    "lambda": r"Lambda",
    "node.js": r"Node(?:\.js)?|node\.js|nodejs",
    "machine learning": r"(?i:machine learning)|ML",
}
_BEFORE = r"(?<![\w+#])"
_AFTER = r"(?![\w+#])"


def _compile_one(body: str) -> re.Pattern:
    return re.compile(f"{_BEFORE}(?:{body}){_AFTER}")


def _key(term: str) -> str:
    return term.strip().lower()


class TermIndex:
    """Lexicon + the user's vocabulary, resolved to canonical keys."""

    def __init__(self, vocabulary: list[str] | None = None, aliases: dict[str, str] | None = None) -> None:
        self._alias_to_key: dict[str, str] = {}
        self._display: dict[str, str] = {}
        self._user_display: dict[str, str] = {}
        for display, alias_list in LEXICON.items():
            key = _key(display)
            self._display[key] = display
            self._alias_to_key[key] = key
            for alias in alias_list:
                self._alias_to_key[_key(alias)] = key
        for alias, target in (aliases or {}).items():
            self._alias_to_key[_key(alias)] = self._alias_to_key.get(_key(target), _key(target))
            self._display.setdefault(self._alias_to_key[_key(alias)], target)
        for term in vocabulary or []:
            self.add_user_term(term)
        self._patterns = self._compile()

    def add_user_term(self, term: str) -> None:
        """Register a warehouse term. "HTML/CSS" registers HTML and CSS."""
        if not term or not term.strip():
            return
        parts = [p for p in re.split(r"\s*/\s*", term) if p] if "/" in term and term != "CI/CD" else [term]
        for part in parts:
            key = self._alias_to_key.get(_key(part))
            if key is None:
                key = _key(part)
                self._alias_to_key[key] = key
                self._display[key] = part.strip()
            # Only a whole (unsplit) user term sets the display form; if the
            # user has several ("C++", "C++20"), the lexicon's name wins.
            if len(parts) == 1 and (key not in self._user_display or term.strip() == self._display.get(key)):
                self._user_display[key] = term.strip()

    def _compile(self) -> list[tuple[str, re.Pattern]]:
        """One pattern per alias, longest first, so "node.js" is claimed
        before "js" can match inside it."""
        by_key: dict[str, list[str]] = {}
        for alias, key in self._alias_to_key.items():
            by_key.setdefault(key, []).append(alias)
        patterns: list[tuple[int, str, re.Pattern]] = []
        for key, alias_list in by_key.items():
            if key in _CASE_SENSITIVE:
                longest = max(len(a) for a in alias_list)
                patterns.append((longest, key, _compile_one(_CASE_SENSITIVE[key])))
                alias_list = [a for a in alias_list if a != key and a not in _AMBIGUOUS_ALIASES]
            for alias in alias_list:
                patterns.append((len(alias), key, _compile_one(f"(?i:{re.escape(alias)})")))
        patterns.sort(key=lambda p: p[0], reverse=True)
        return [(key, pat) for _, key, pat in patterns]

    def expand(self, keys) -> set[str]:
        """keys plus everything they imply (see IMPLIES)."""
        out = set(keys)
        for k in keys:
            out.update(IMPLIES.get(k, []))
        return out

    def key(self, term: str) -> str:
        return self._alias_to_key.get(_key(term), _key(term))

    def display(self, key: str) -> str:
        return self._user_display.get(key) or self._display.get(key, key)

    def find(self, text: str) -> list[str]:
        """Canonical keys mentioned in text, in order of first appearance."""
        return list(dict.fromkeys(key for _, _, key in self.find_spans(text)))

    def find_spans(self, text: str) -> list[tuple[int, int, str]]:
        """(start, end, key) for every mention, in text order."""
        if not text:
            return []
        masked = list(text)
        hits: list[tuple[int, int, str]] = []
        for key, pattern in self._patterns:
            current = "".join(masked)
            for m in pattern.finditer(current):
                if m.end() == m.start():
                    continue
                hits.append((m.start(), m.end(), key))
                masked[m.start():m.end()] = " " * (m.end() - m.start())
        hits.sort()
        return hits


# Aliases that are ordinary words; handled by the case-sensitive pattern only.
_AMBIGUOUS_ALIASES = {"node", "ml"}
