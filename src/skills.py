# Diccionario con términos complementarios ÚNICAMENTE (sin repetir los anteriores)
# Explorando subsectores adyacentes: e-commerce, logística, administración pública, ciberseguridad, DevOps, marketing digital/ventas, etc.
# Generador de archivo yaml a partir de un script de python.

keywords_data = {
    "competencias": {
        "atencion_cliente": [
            "atención al público", "atención al cliente", "trato con clientes", "servicio al cliente", 
            "orientación al cliente", "orientado al cliente", "fidelización de clientes", "recepción de clientes",
            "atención telefónica", "trato amable", "atención y soporte técnico a clientes", "cara amable"
        ],
        "trabajo_equipo": [
            "trabajo en equipo", "colaboración", "capacidad para colaborar", "entorno colaborativo",
            "cooperación", "espíritu de equipo", "trabajar en equipo", "capacidad de trabajo en equipo"
        ],
        "organizacion": [
            "organización", "capacidad organizativa", "planificación de tareas", "organizado",
            "gestión del tiempo", "metódico", "planificación", "priorización de tareas", "persona organizada"
        ],
        "resolucion_problemas": [
            "resolución de problemas", "capacidad de resolución", "toma de decisiones", "resolución de incidencias",
            "solución de conflictos", "gestión de quejas", "capacidad para resolver incidencias", "resolución de problemas técnicos"
        ],
        "comunicacion": [
            "habilidad para comunicarte", "comunicación clara", "comunicación efectiva", "habilidades comunicativas",
            "escucha activa", "empatía", "comunicación asertiva"
        ],
        "gestion_proyectos": [
            "gestión de proyectos", "project management", "metodologías ágiles", "scrum", "kanban",
            "planificación de proyectos", "seguimiento de hitos", "control de presupuestos", "gestión de stakeholders",
            "product manager"
        ],
        "administracion_redes": [
            "administración de sistemas", "administración de redes", "mantenimiento de servidores", "configuración de routers",
            "seguridad informática", "gestión de infraestructura", "monitoreo de redes"
        ]
    },
    "conocimientos": {
        "caja_registradora": [
            "manejo de caja", "uso de caja registradora", "cobro en caja", "apertura y cierre de la caja",
            "arqueo de caja", "operaciones de caja", "cobro de equipajes", "cajero reponedor"
        ],
        "reposicion": [
            "reposición de producto", "reposición de stock", "gestión de inventario", "tareas de reposición",
            "reponedor", "abastecer los lineales", "colocar precios", "colocar carteles", "retirar productos no aptos",
            "etiquetado", "limpieza de las zonas de trabajo", "orden y la limpieza"
        ],
        "idiomas_ingles": [
            "inglés", "nivel de inglés", "inglés hablado y escrito", "inglés alto", "bilingüe inglés",
            "conocimiento de otros idiomas", "idioma extranjero"
        ],
        "contabilidad_facturacion": [
            "contabilidad", "facturación", "gestión de facturas", "asientos contables", "conciliación bancaria",
            "balances", "cuentas por pagar", "cuentas por cobrar", "administrativo contable", "administrativo facturación"
        ],
        "desarrollo_software": [
            "desarrollo python", "programación", "código limpio", "estructuras de datos", "backend",
            "desarrollo de software", "apis REST", "django", "flask"
        ],
        "sistemas_operativos": [
            "windows", "linux", "sistemas windows/linux", "administración de so", "instalación de sistemas"
        ],
        "redes_telecomunicaciones": [
            "redes tcp/ip", "comunicaciones", "enrutamiento", "direccionalidad ip", "redes locales", "lan/wan"
        ],
        "soporte_it": [
            "soporte técnico", "helpdesk", "asistencia técnica", "servicio de asistencia técnica", "sat",
            "instalación y configuración de equipos", "dispositivos de pago", "mantenimiento preventivo",
            "mantenimiento correctivo", "microinformática", "smr", "asir", "técnico informático", "técnico de soporte"
        ],
        "hosteleria_turismo": [
            "cambrers", "camarero", "ayudante de camarero", "ayudante de sala", "servicio de mesa",
            "recepcionista de hotel", "check-in", "check-out", "reservas", "atención a pasajeros", "embarque de pasajeros"
        ]
    },
    "herramientas": {
        "paquete_office": [
            "microsoft office", "paquete office", "excel", "word", "powerpoint", "hojas de cálculo"
        ],
        "tpv": [
            "tpv", "terminal punto de venta", "software de punto de venta", "sistemas de pago", "datáfono"
        ],
        "ticketing": [
            "herramientas de ticketing", "gestión de tickets", "jira", "glpi", "servicenow", "zendesk",
            "seguimiento y gestión de incidencias"
        ],
        "telemetria_remota": [
            "plataformas de telemetría", "soporte remoto", "anydesk", "teamviewer", "sistemas conectados"
        ]
    },
    "softskills": {
        "proactividad": [
            "proactividad", "actitud proactiva", "iniciativa", "ganas de aprender", "motivación por aprender",
            "autonomía", "persona proactiva", "actitud positiva", "ganas y más ganas de aprender", "evolucionar profesionalmente"
        ],
        "flexibilidad_horaria": [
            "disponibilidad horaria", "flexibilidad de horario", "turnos rotativos", "disponibilidad para trabajar fines de semana",
            "horario rotativo", "flexibilidad horaria"
        ],
        "orientacion_detalle": [
            "orientación al detalle", "minuciosidad", "precisión", "organizada", "atención al detalle"
        ],
        "tolerancia_presion": [
            "trabajo bajo presión", "entorno dinámico", "tolerancia al estrés", "ritmo rápido",
            "operación que no se detiene"
        ]
    }
}

# Generar archivo YAML en formato de texto puro
yaml_content = []
for category, subcategories in keywords_data.items():
    yaml_content.append(f"{category}:")
    for subcat, terms in subcategories.items():
        yaml_content.append(f"  {subcat}:")
        for term in terms:
            yaml_content.append(f"    - \"{term}\"")

yaml_file_path = "palabras_clave_ofertas.yaml"
with open(yaml_file_path, "w", encoding="utf-8") as file:
    file.write("\n".join(yaml_content))

print("YAML generado correctamente.")


#SEGUNDO SCRIPT CON MAS COMPETENCIAS
'''
# Diccionario con términos complementarios ÚNICAMENTE (sin repetir los anteriores)
# Explorando subsectores adyacentes: e-commerce, logística, administración pública, ciberseguridad, DevOps, marketing digital/ventas, etc.

nuevos_terminos = {
    "competencias": {
        "negociacion_ventas": [
            "orientación a resultados", "cierre de ventas", "captación de clientes", "negociación comercial",
            "venta consultiva", "gestión de leads", "fidelización de cuentas", "técnicas de venta", "televenta"
        ],
        "logistica_almacen": [
            "gestión de almacén", "preparación de pedidos", "picking y packing", "control de stock",
            "recepción de mercancías", "logística interna", "expedición de pedidos", "inventariado masivo"
        ],
        "seguridad_datos": [
            "auditoría de sistemas", "análisis de vulnerabilidades", "ciberseguridad", "gestión de accesos",
            "cumplimiento de RGPD", "protección de datos", "copias de seguridad", "políticas de seguridad"
        ],
        "automatizacion_procesos": [
            "automatización de tareas", "despliegue continuo", "ci/cd", "infraestructura como código",
            "optimización de flujos", "digitalización de procesos", "gestión del cambio"
        ]
    },
    "conocimientos": {
        "administracion_publica_legal": [
            "gestión documental", "tramitación administrativa", "procedimiento administrativo", "archivo de expedientes",
            "presentación de escritos", "licitaciones públicas", "subvenciones", "legislación laboral"
        ],
        "ecommerce_marketing": [
            "marketing digital", "gestión de e-commerce", "posicionamiento seo", "campañas sem",
            "analítica web", "redes sociales corporativas", "estrategia de contenido", "pasarelas de pago online"
        ],
        "finanzas_fiscalidad": [
            "gestión de tesorería", "liquidación de impuestos", "iva e irpf", "auditoría interna",
            "control de costes", "análisis financiero", "contabilidad analítica", "modelos fiscales"
        ],
        "entornos_cloud_devops": [
            "cloud computing", "arquitectura en la nube", "contenedores", "orquestación",
            "virtualización", "microservicios", "administración cloud"
        ],
        "atencion_sanitaria_bienestar": [
            "recepción clínica", "gestión de citas", "atención al paciente", "primeros auxilios",
            "gestión de historiales", "atención sociosanitaria"
        ]
    },
    "herramientas": {
        "sistemas_erp_crm": [
            "sap", "salesforce", "odoo", "microsoft dynamics", "oracle", "hubspot",
            "software erp", "sistema crm", "albaranes digitales"
        ],
        "herramientas_cloud_devops": [
            "aws", "azure", "google cloud platform", "docker", "kubernetes", "ansible",
            "terraform", "git", "github", "gitlab"
        ],
        "bases_datos": [
            "sql", "mysql", "postgresql", "oracle db", "mongodb", "consultas sql",
            "administración de bases de datos"
        ],
        "analisis_datos_bi": [
            "power bi", "tableau", "google analytics", "data studio", "extracción de datos"
        ]
    },
    "softskills": {
        "resiliencia_adaptabilidad": [
            "adaptabilidad al cambio", "resiliencia", "flexibilidad cognitiva", "tolerancia a la frustración",
            "capacidad de aprendizaje rápido", "gestión de la incertidumbre"
        ],
        "liderazgo_influencia": [
            "capacidad de liderazgo", "gestión de equipos", "toma de iniciativas", "habilidades de negociación",
            "capacidad de persuasión", "resolución de conflictos internos", "mentoría"
        ],
        "creatividad_innovación": [
            "pensamiento crítico", "creatividad", "resolución creativa de problemas", "mentalidad de crecimiento",
            "innovación continua"
        ]
    }
}

# Generar el archivo YAML complementario -v2 de forma manual
yaml_content_v2 = []
for category, subcategories in nuevos_terminos.items():
    yaml_content_v2.append(f"{category}:")
    for subcat, terms in subcategories.items():
        yaml_content_v2.append(f"  {subcat}:")
        for term in terms:
            yaml_content_v2.append(f"    - \"{term}\"")

yaml_file_path_v2 = "palabras_clave_ofertas-v2.yaml"
with open(yaml_file_path_v2, "w", encoding="utf-8") as file:
    file.write("\n".join(yaml_content_v2))

print("YAML complementario v2 generado correctamente.")
'''
