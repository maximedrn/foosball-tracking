\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{report}[]
\LoadClass[11pt,a4paper]{article}

\RequirePackage[margin=2.2cm]{geometry}
\RequirePackage{indentfirst}
\RequirePackage{enumitem}
\RequirePackage{titlesec}
\RequirePackage{array}
\RequirePackage{booktabs}
\RequirePackage{longtable}
\RequirePackage{needspace}
\RequirePackage{xcolor}
\RequirePackage{svg}
\svgsetup{inkscapepath=./build/svg-inkscape/}
\definecolor{linkBlue}{HTML}{245D86}
\definecolor{priorityHigh}{HTML}{A33A3A}
\definecolor{priorityMedium}{HTML}{98700E}
\definecolor{priorityLow}{HTML}{3D7657}

\setlength{\emergencystretch}{2em}
\linespread{1.09}
\raggedbottom
\pagestyle{empty}
\setlist[itemize]{leftmargin=1.75em,itemsep=0.28em,topsep=0.38em,parsep=0.08em}
\titleformat{\section}{\Large\bfseries}{\thesection.}{0.6em}{}
\titlespacing*{\section}{0pt}{1.65em}{0.70em}
\titleformat{\subsection}{\large\bfseries}{\thesubsection}{0.7em}{}
\titlespacing*{\subsection}{0pt}{1.27em}{0.49em}
\newcolumntype{L}[1]{>{\raggedright\arraybackslash}p{#1}}
\setlength{\tabcolsep}{4.5pt}
\renewcommand{\arraystretch}{1.36}

\AtBeginDocument{%
  \setlength{\parindent}{1.25em}%
  \setlength{\parskip}{0.48em}%
  \hypersetup{colorlinks=true,breaklinks=true,linkcolor=linkBlue,urlcolor=linkBlue,citecolor=linkBlue}%
}
