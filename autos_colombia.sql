--
-- PostgreSQL database dump
--

\restrict J4VEFfgxYo6r52t2UAlTDxY88BBmqDbSkYfFwmtYBRXAlzVMulbEjaTWWFk4U77

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

-- Started on 2026-11-03 15:06:35

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 219 (class 1259 OID 16579)
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 16722)
-- Name: auditoria; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.auditoria (
    id bigint NOT NULL,
    operador_id bigint NOT NULL,
    accion text NOT NULL,
    entidad text NOT NULL,
    entidad_id bigint,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    detalle jsonb,
    CONSTRAINT ck_auditoria_accion_no_vacia CHECK ((accion ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_auditoria_entidad_no_vacia CHECK ((entidad ~ '[^[:space:]]'::text))
);


ALTER TABLE public.auditoria OWNER TO postgres;

--
-- TOC entry 230 (class 1259 OID 16721)
-- Name: auditoria_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.auditoria ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.auditoria_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 223 (class 1259 OID 16608)
-- Name: celda; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.celda (
    id bigint NOT NULL,
    codigo text NOT NULL,
    tipo text NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_celda_codigo_no_vacio CHECK ((codigo ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_celda_codigo_normalizado CHECK ((codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text)))),
    CONSTRAINT ck_celda_tipo_no_vacio CHECK ((tipo ~ '[^[:space:]]'::text))
);


ALTER TABLE public.celda OWNER TO postgres;

--
-- TOC entry 222 (class 1259 OID 16607)
-- Name: celda_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.celda ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.celda_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 233 (class 1259 OID 16747)
-- Name: cliente; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.cliente (
    id bigint NOT NULL,
    documento text NOT NULL,
    nombre text NOT NULL,
    telefono text NOT NULL,
    correo text NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_cliente_correo_formato CHECK ((correo ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'::text)),
    CONSTRAINT ck_cliente_correo_no_vacio CHECK ((correo ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_documento_no_vacio CHECK ((documento ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_nombre_no_vacio CHECK ((nombre ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_cliente_telefono_no_vacio CHECK ((telefono ~ '[^[:space:]]'::text))
);


ALTER TABLE public.cliente OWNER TO postgres;

--
-- TOC entry 232 (class 1259 OID 16746)
-- Name: cliente_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.cliente ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.cliente_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 227 (class 1259 OID 16637)
-- Name: estancia; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.estancia (
    id bigint NOT NULL,
    vehiculo_id bigint NOT NULL,
    celda_id bigint NOT NULL,
    entrada timestamp with time zone DEFAULT now() NOT NULL,
    salida timestamp with time zone,
    operador_entrada_id bigint NOT NULL,
    operador_salida_id bigint,
    ficho_codigo text,
    ficho_usado_en timestamp with time zone,
    puerta_entrada_id bigint,
    puerta_salida_id bigint,
    CONSTRAINT ck_estancia_cierre_completo CHECK (((salida IS NULL) = (operador_salida_id IS NULL))),
    CONSTRAINT ck_estancia_ficho_fecha CHECK (((ficho_usado_en IS NULL) OR (ficho_usado_en >= entrada))),
    CONSTRAINT ck_estancia_ficho_formato CHECK (((ficho_codigo IS NULL) OR (ficho_codigo ~ '^AC-[0-9]{8}-[0-9]{4}$'::text))),
    CONSTRAINT ck_estancia_ficho_uso CHECK (((ficho_usado_en IS NULL) OR (ficho_codigo IS NOT NULL))),
    CONSTRAINT ck_estancia_orden_fechas CHECK ((salida >= entrada))
);


ALTER TABLE public.estancia OWNER TO postgres;

--
-- TOC entry 226 (class 1259 OID 16636)
-- Name: estancia_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.estancia ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.estancia_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 237 (class 1259 OID 16800)
-- Name: estancia_reasignacion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.estancia_reasignacion (
    id bigint NOT NULL,
    estancia_id bigint NOT NULL,
    celda_anterior_id bigint NOT NULL,
    celda_nueva_id bigint NOT NULL,
    operador_id bigint NOT NULL,
    fecha timestamp with time zone DEFAULT now() NOT NULL,
    motivo text,
    CONSTRAINT ck_reasignacion_motivo_no_vacio CHECK (((motivo IS NULL) OR (motivo ~ '[^[:space:]]'::text)))
);


ALTER TABLE public.estancia_reasignacion OWNER TO postgres;

--
-- TOC entry 236 (class 1259 OID 16799)
-- Name: estancia_reasignacion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.estancia_reasignacion ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.estancia_reasignacion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 225 (class 1259 OID 16624)
-- Name: operador; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.operador (
    id bigint NOT NULL,
    nombre text NOT NULL,
    telefono text NOT NULL,
    usuario text NOT NULL,
    contrasena_hash text NOT NULL,
    rol text DEFAULT 'OPERADOR'::text NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_operador_contrasena_no_vacia CHECK ((contrasena_hash ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_operador_nombre_no_vacio CHECK ((nombre ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_operador_rol CHECK ((rol = ANY (ARRAY['ADMINISTRADOR'::text, 'OPERADOR'::text]))),
    CONSTRAINT ck_operador_telefono_no_vacio CHECK ((telefono ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_operador_usuario_longitud CHECK (((char_length(usuario) >= 3) AND (char_length(usuario) <= 50))),
    CONSTRAINT ck_operador_usuario_no_vacio CHECK ((usuario ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_operador_usuario_normalizado CHECK ((usuario = lower(regexp_replace(usuario, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text))))
);


ALTER TABLE public.operador OWNER TO postgres;

--
-- TOC entry 224 (class 1259 OID 16623)
-- Name: operador_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.operador ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.operador_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 235 (class 1259 OID 16782)
-- Name: puerta; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.puerta (
    id bigint NOT NULL,
    codigo text NOT NULL,
    ubicacion text NOT NULL,
    activo boolean DEFAULT true NOT NULL,
    CONSTRAINT ck_puerta_codigo_no_vacio CHECK ((codigo ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_puerta_codigo_normalizado CHECK ((codigo = upper(regexp_replace(codigo, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text)))),
    CONSTRAINT ck_puerta_ubicacion_no_vacia CHECK ((ubicacion ~ '[^[:space:]]'::text))
);


ALTER TABLE public.puerta OWNER TO postgres;

--
-- TOC entry 234 (class 1259 OID 16781)
-- Name: puerta_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.puerta ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.puerta_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 229 (class 1259 OID 16677)
-- Name: registro; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.registro (
    id bigint NOT NULL,
    vehiculo_id bigint NOT NULL,
    celda_id bigint NOT NULL,
    operador_id bigint NOT NULL,
    fecha_ingreso timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    fecha_salida timestamp with time zone,
    estado character varying(20) DEFAULT 'ABIERTO'::character varying NOT NULL
);


ALTER TABLE public.registro OWNER TO postgres;

--
-- TOC entry 228 (class 1259 OID 16676)
-- Name: registro_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.registro_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.registro_id_seq OWNER TO postgres;

--
-- TOC entry 5194 (class 0 OID 0)
-- Dependencies: 228
-- Name: registro_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.registro_id_seq OWNED BY public.registro.id;


--
-- TOC entry 239 (class 1259 OID 16850)
-- Name: sesion; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sesion (
    id bigint NOT NULL,
    operador_id bigint NOT NULL,
    token_hash text NOT NULL,
    creada_en timestamp with time zone DEFAULT now() NOT NULL,
    expira_en timestamp with time zone NOT NULL,
    revocada_en timestamp with time zone,
    CONSTRAINT ck_sesion_fechas CHECK ((expira_en > creada_en)),
    CONSTRAINT ck_sesion_revocada CHECK (((revocada_en IS NULL) OR (revocada_en >= creada_en))),
    CONSTRAINT ck_sesion_token_hash_formato CHECK ((token_hash ~ '^[0-9a-f]{64}$'::text))
);


ALTER TABLE public.sesion OWNER TO postgres;

--
-- TOC entry 238 (class 1259 OID 16849)
-- Name: sesion_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.sesion ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.sesion_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 221 (class 1259 OID 16586)
-- Name: vehiculo; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.vehiculo (
    id bigint NOT NULL,
    placa text NOT NULL,
    color text NOT NULL,
    modelo integer NOT NULL,
    marca text NOT NULL,
    tipo text NOT NULL,
    cliente_id bigint,
    CONSTRAINT ck_vehiculo_color_no_vacio CHECK ((color ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_marca_no_vacia CHECK ((marca ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_modelo_anio CHECK (((modelo >= 1) AND (modelo <= 9999))),
    CONSTRAINT ck_vehiculo_placa_no_vacia CHECK ((placa ~ '[^[:space:]]'::text)),
    CONSTRAINT ck_vehiculo_placa_normalizada CHECK ((placa = upper(regexp_replace(placa, '^[[:space:]]+|[[:space:]]+$'::text, ''::text, 'g'::text)))),
    CONSTRAINT ck_vehiculo_tipo CHECK ((tipo = ANY (ARRAY['MOTO'::text, 'AUTOMOVIL'::text, 'CAMIONETA'::text])))
);


ALTER TABLE public.vehiculo OWNER TO postgres;

--
-- TOC entry 220 (class 1259 OID 16585)
-- Name: vehiculo_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

ALTER TABLE public.vehiculo ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.vehiculo_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- TOC entry 4909 (class 2604 OID 16680)
-- Name: registro id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.registro ALTER COLUMN id SET DEFAULT nextval('public.registro_id_seq'::regclass);


--
-- TOC entry 5168 (class 0 OID 16579)
-- Dependencies: 219
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
0009
\.


--
-- TOC entry 5180 (class 0 OID 16722)
-- Dependencies: 231
-- Data for Name: auditoria; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.auditoria (id, operador_id, accion, entidad, entidad_id, fecha, detalle) FROM stdin;
1	2	CREAR	operador	2	2026-10-30 11:58:51.030577-05	{"rol": "ADMINISTRADOR", "activo": true, "origen": "bootstrap"}
56	2	CREAR	operador	39	2026-10-30 13:59:34.694913-05	{"rol": "OPERADOR", "activo": true}
57	39	LOGIN	sesion	39	2026-10-30 13:59:57.354994-05	{"rol": "OPERADOR"}
58	2	LOGIN	sesion	2	2026-10-30 14:00:47.935259-05	{"rol": "ADMINISTRADOR"}
59	2	LOGIN	sesion	2	2026-10-30 14:02:42.275726-05	{"rol": "ADMINISTRADOR"}
60	2	ACTUALIZAR	operador	39	2026-10-30 14:02:59.033988-05	{"campos": ["telefono"]}
61	39	LOGIN	sesion	39	2026-10-30 14:03:14.264406-05	{"rol": "OPERADOR"}
62	2	LOGIN	sesion	2	2026-10-30 14:11:01.938996-05	{"rol": "ADMINISTRADOR"}
226	2	LOGIN	sesion	2	2026-10-30 15:12:25.663992-05	{"rol": "ADMINISTRADOR"}
227	2	SALIDA	estancia	54	2026-10-30 15:14:33.118203-05	{"placa": "M165", "celda_id": 202}
228	2	ENTRADA	estancia	81	2026-10-30 15:15:28.326506-05	{"placa": "M165", "celda_id": 124}
229	39	LOGIN	sesion	39	2026-10-30 15:15:56.115645-05	{"rol": "OPERADOR"}
230	2	LOGIN	sesion	2	2026-10-30 15:21:29.576605-05	{"rol": "ADMINISTRADOR"}
231	39	LOGIN	sesion	39	2026-10-30 15:26:25.019029-05	{"rol": "OPERADOR"}
232	2	LOGIN	sesion	2	2026-10-30 15:28:09.67779-05	{"rol": "ADMINISTRADOR"}
233	2	ACTUALIZAR	vehiculo	86	2026-10-30 15:40:54.23768-05	{"campos": ["placa"]}
234	39	LOGIN	sesion	39	2026-10-30 15:41:13.392859-05	{"rol": "OPERADOR"}
235	2	LOGIN	sesion	2	2026-11-03 09:24:07.628185-05	{"rol": "ADMINISTRADOR"}
547	39	ENTRADA	estancia	208	2026-11-03 12:02:37.972513-05	{"placa": "M165", "celda_id": 197, "ficho_codigo": "AC-20261103-0002", "puerta_entrada_id": 1}
548	39	LOGIN	sesion	3	2026-11-03 13:11:09.859764-05	{"rol": "OPERADOR", "expira_en": "2026-11-03T19:11:10.110196+00:00"}
550	2	LOGIN	sesion	4	2026-11-03 13:14:32.11584-05	{"rol": "ADMINISTRADOR", "expira_en": "2026-11-03T19:14:32.353558+00:00"}
552	39	LOGIN	sesion	5	2026-11-03 13:56:15.706543-05	{"rol": "OPERADOR", "expira_en": "2026-11-03T19:56:16.059595+00:00"}
553	39	ACTUALIZAR	cliente	221	2026-11-03 14:19:14.104106-05	{"campos": ["activo"], "nuevos": {"activo": false}, "anteriores": {"activo": true}}
556	2	LOGIN	sesion	6	2026-11-03 14:39:38.402077-05	{"rol": "ADMINISTRADOR", "expira_en": "2026-11-03T20:39:38.658539+00:00"}
558	2	ENTRADA	estancia	209	2026-11-03 14:40:20.760312-05	{"placa": "M167", "celda_id": 184, "ficho_codigo": "AC-20261103-0003", "puerta_entrada_id": 2}
560	2	CREAR	cliente	266	2026-11-03 14:42:10.067099-05	{"nuevos": {"activo": true, "correo": "operador@gmail.com", "nombre": "pepito", "telefono": "3120000000", "documento": "1111111111"}}
561	2	ACTUALIZAR	vehiculo	420	2026-11-03 14:42:21.512871-05	{"campos": ["cliente_id"], "nuevos": {"cliente_id": 266}, "anteriores": {"cliente_id": 221}}
563	2	LOGOUT	sesion	6	2026-11-03 14:49:23.664284-05	{"rol": "ADMINISTRADOR"}
565	39	ACTUALIZAR	cliente	266	2026-11-03 14:50:40.538011-05	{"campos": ["activo"], "nuevos": {"activo": false}, "anteriores": {"activo": true}}
567	39	LOGOUT	sesion	7	2026-11-03 14:51:00.998601-05	{"rol": "OPERADOR"}
151	2	DESACTIVAR	celda	1	2026-10-30 14:37:11.89477-05	{"motivo": "con_estancias", "activo_nuevo": false, "activo_anterior": true}
152	39	LOGIN	sesion	39	2026-10-30 14:39:07.184251-05	{"rol": "OPERADOR"}
153	39	CREAR	vehiculo	86	2026-10-30 14:39:39.544058-05	{"tipo": "AUTOMOVIL", "placa": "M165"}
154	39	ENTRADA	estancia	54	2026-10-30 14:40:01.475554-05	{"placa": "M165", "celda_id": 202}
155	39	LOGIN	sesion	39	2026-10-30 14:43:36.454819-05	{"rol": "OPERADOR"}
52	2	LOGIN	sesion	2	2026-10-30 13:39:18.656364-05	{"rol": "ADMINISTRADOR"}
53	2	ACTUALIZAR	operador	2	2026-10-30 13:41:15.168475-05	{"campos": ["nombre"]}
54	2	LOGIN	sesion	2	2026-10-30 13:42:17.633524-05	{"rol": "ADMINISTRADOR"}
488	2	LOGIN	sesion	1	2026-11-03 11:13:32.384548-05	{"rol": "ADMINISTRADOR", "expira_en": "2026-11-03T17:13:32.624393+00:00"}
489	2	CREAR	cliente	221	2026-11-03 11:16:58.17967-05	{"nuevos": {"activo": true, "correo": "caro@gmail.com", "nombre": "carolina velasquez avilaaa", "telefono": "3206897319", "documento": "1028031780"}}
490	2	ACTUALIZAR	vehiculo	86	2026-11-03 11:17:21.299735-05	{"campos": ["cliente_id"], "nuevos": {"cliente_id": 221}, "anteriores": {"cliente_id": null}}
491	2	REASIGNAR	estancia	81	2026-11-03 11:21:42.460727-05	{"placa": "M166", "motivo": "Se reasigna para entregar fichos.", "celda_nueva_id": 125, "celda_anterior_id": 124}
492	2	CREAR	vehiculo	371	2026-11-03 11:22:38.963794-05	{"nuevos": {"tipo": "MOTO", "color": "negro", "marca": "navi", "placa": "M165", "modelo": 2025, "cliente_id": 221}}
493	2	ENTRADA	estancia	186	2026-11-03 11:23:07.13445-05	{"placa": "M165", "celda_id": 199, "ficho_codigo": "AC-20261103-0001", "puerta_entrada_id": 1}
494	2	LOGOUT	sesion	1	2026-11-03 11:25:29.805175-05	{"rol": "ADMINISTRADOR"}
495	39	LOGIN	sesion	2	2026-11-03 11:25:40.348247-05	{"rol": "OPERADOR", "expira_en": "2026-11-03T17:25:40.580068+00:00"}
496	39	SALIDA	estancia	186	2026-11-03 11:27:05.176118-05	{"placa": "M165", "celda_id": 199, "ficho_codigo": "AC-20261103-0001", "puerta_salida_id": 2}
549	39	LOGOUT	sesion	3	2026-11-03 13:14:23.894291-05	{"rol": "OPERADOR"}
551	2	LOGOUT	sesion	4	2026-11-03 13:56:03.164451-05	{"rol": "ADMINISTRADOR"}
554	39	ACTUALIZAR	cliente	221	2026-11-03 14:19:19.059902-05	{"campos": ["activo"], "nuevos": {"activo": true}, "anteriores": {"activo": false}}
555	39	LOGOUT	sesion	5	2026-11-03 14:28:32.465259-05	{"rol": "OPERADOR"}
557	2	CREAR	vehiculo	420	2026-11-03 14:40:11.671109-05	{"nuevos": {"tipo": "AUTOMOVIL", "color": "blanco", "marca": "mazda", "placa": "M167", "modelo": 2026, "cliente_id": 221}}
559	2	SALIDA	estancia	209	2026-11-03 14:41:01.195508-05	{"placa": "M167", "celda_id": 184, "ficho_codigo": "AC-20261103-0003", "puerta_salida_id": 2}
562	2	ENTRADA	estancia	210	2026-11-03 14:43:05.253097-05	{"placa": "M167", "celda_id": 189, "ficho_codigo": "AC-20261103-0004", "puerta_entrada_id": 1}
564	39	LOGIN	sesion	7	2026-11-03 14:49:55.754222-05	{"rol": "OPERADOR", "expira_en": "2026-11-03T20:49:55.997087+00:00"}
566	39	ACTUALIZAR	cliente	266	2026-11-03 14:50:49.078616-05	{"campos": ["activo"], "nuevos": {"activo": true}, "anteriores": {"activo": false}}
\.


--
-- TOC entry 5172 (class 0 OID 16608)
-- Dependencies: 223
-- Data for Name: celda; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.celda (id, codigo, tipo, activo) FROM stdin;
124	C-01	AUTOMOVIL	t
125	C-02	AUTOMOVIL	t
126	C-03	AUTOMOVIL	t
127	C-04	AUTOMOVIL	t
128	C-05	AUTOMOVIL	t
129	C-06	AUTOMOVIL	t
130	C-07	AUTOMOVIL	t
131	C-08	AUTOMOVIL	t
132	C-09	AUTOMOVIL	t
133	C-10	AUTOMOVIL	t
134	C-11	AUTOMOVIL	t
135	C-12	AUTOMOVIL	t
136	C-13	AUTOMOVIL	t
137	C-14	AUTOMOVIL	t
138	C-15	AUTOMOVIL	t
139	C-16	AUTOMOVIL	t
140	C-17	AUTOMOVIL	t
141	C-18	AUTOMOVIL	t
142	C-19	AUTOMOVIL	t
143	C-20	AUTOMOVIL	t
144	C-21	AUTOMOVIL	t
145	C-22	AUTOMOVIL	t
146	C-23	AUTOMOVIL	t
147	C-24	AUTOMOVIL	t
148	C-25	AUTOMOVIL	t
149	C-26	AUTOMOVIL	t
150	C-27	AUTOMOVIL	t
151	C-28	AUTOMOVIL	t
152	C-29	AUTOMOVIL	t
153	C-30	AUTOMOVIL	t
154	C-31	AUTOMOVIL	t
155	C-32	AUTOMOVIL	t
156	C-33	AUTOMOVIL	t
157	C-34	AUTOMOVIL	t
158	C-35	AUTOMOVIL	t
159	C-36	AUTOMOVIL	t
160	C-37	AUTOMOVIL	t
161	C-38	AUTOMOVIL	t
162	C-39	AUTOMOVIL	t
163	C-40	AUTOMOVIL	t
164	C-41	AUTOMOVIL	t
165	C-42	AUTOMOVIL	t
166	C-43	AUTOMOVIL	t
167	C-44	AUTOMOVIL	t
168	C-45	AUTOMOVIL	t
169	C-46	AUTOMOVIL	t
170	C-47	AUTOMOVIL	t
171	C-48	AUTOMOVIL	t
172	C-49	AUTOMOVIL	t
173	C-50	AUTOMOVIL	t
174	C-51	AUTOMOVIL	t
175	C-52	AUTOMOVIL	t
176	C-53	AUTOMOVIL	t
177	C-54	AUTOMOVIL	t
178	C-55	AUTOMOVIL	t
179	C-56	AUTOMOVIL	t
180	C-57	AUTOMOVIL	t
181	C-58	AUTOMOVIL	t
182	C-59	AUTOMOVIL	t
183	C-60	AUTOMOVIL	t
184	C-61	AUTOMOVIL	t
185	C-62	AUTOMOVIL	t
186	C-63	AUTOMOVIL	t
187	C-64	AUTOMOVIL	t
188	C-65	AUTOMOVIL	t
189	C-66	AUTOMOVIL	t
190	C-67	AUTOMOVIL	t
191	C-68	AUTOMOVIL	t
192	C-69	AUTOMOVIL	t
193	C-70	AUTOMOVIL	t
194	M-01	MOTO	t
195	M-02	MOTO	t
196	M-03	MOTO	t
197	M-04	MOTO	t
198	M-05	MOTO	t
199	M-06	MOTO	t
200	M-07	MOTO	t
201	M-08	MOTO	t
202	M-09	MOTO	t
203	M-10	MOTO	t
1	A-01	MOTO	f
\.


--
-- TOC entry 5182 (class 0 OID 16747)
-- Dependencies: 233
-- Data for Name: cliente; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cliente (id, documento, nombre, telefono, correo, activo) FROM stdin;
221	1028031780	carolina velasquez avilaaa	3206897319	caro@gmail.com	t
266	1111111111	pepito	3120000000	operador@gmail.com	t
\.


--
-- TOC entry 5176 (class 0 OID 16637)
-- Dependencies: 227
-- Data for Name: estancia; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.estancia (id, vehiculo_id, celda_id, entrada, salida, operador_entrada_id, operador_salida_id, ficho_codigo, ficho_usado_en, puerta_entrada_id, puerta_salida_id) FROM stdin;
1	1	1	2026-10-23 08:55:31.60898-05	\N	1	\N	\N	\N	\N	\N
208	371	197	2026-11-03 12:02:37.991588-05	\N	39	\N	AC-20261103-0002	\N	1	\N
209	420	184	2026-11-03 14:40:20.791509-05	2026-11-03 14:41:01.206486-05	2	2	AC-20261103-0003	2026-11-03 14:41:01.206486-05	2	2
210	420	189	2026-11-03 14:43:05.270914-05	\N	2	\N	AC-20261103-0004	\N	1	\N
81	86	125	2026-10-30 15:15:28.337457-05	\N	2	\N	\N	\N	\N	\N
186	371	199	2026-11-03 11:23:07.159218-05	2026-11-03 11:27:05.183246-05	2	39	AC-20261103-0001	2026-11-03 11:27:05.183246-05	1	2
54	86	202	2026-10-30 14:40:01.483591-05	2026-10-30 15:14:33.125001-05	39	2	\N	\N	\N	\N
\.


--
-- TOC entry 5186 (class 0 OID 16800)
-- Dependencies: 237
-- Data for Name: estancia_reasignacion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.estancia_reasignacion (id, estancia_id, celda_anterior_id, celda_nueva_id, operador_id, fecha, motivo) FROM stdin;
16	81	124	125	2	2026-11-03 11:21:42.478092-05	Se reasigna para entregar fichos.
\.


--
-- TOC entry 5174 (class 0 OID 16624)
-- Dependencies: 225
-- Data for Name: operador; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.operador (id, nombre, telefono, usuario, contrasena_hash, rol, activo) FROM stdin;
1	Andres Grisales	3147683830	operador-1	!	OPERADOR	f
2	carolina velasquez avila	3206897318	admin	$2b$12$nI4D5AFhy0W3.dUkstBRGuy2YdQV/4RPLdsGeOf4qtmy.8whN3/FK	ADMINISTRADOR	t
39	Johnatan Velez	3002228899	operador1	$2b$12$L7zIb1X.FGg29Kvll9SP.uUxarXp0dKC3Rq0lqenPTtDG/Hny1boK	OPERADOR	t
\.


--
-- TOC entry 5184 (class 0 OID 16782)
-- Dependencies: 235
-- Data for Name: puerta; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.puerta (id, codigo, ubicacion, activo) FROM stdin;
1	NORTE	Entrada Norte	t
2	SUR	Entrada Sur	t
\.


--
-- TOC entry 5178 (class 0 OID 16677)
-- Dependencies: 229
-- Data for Name: registro; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.registro (id, vehiculo_id, celda_id, operador_id, fecha_ingreso, fecha_salida, estado) FROM stdin;
\.


--
-- TOC entry 5188 (class 0 OID 16850)
-- Dependencies: 239
-- Data for Name: sesion; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.sesion (id, operador_id, token_hash, creada_en, expira_en, revocada_en) FROM stdin;
1	2	352d4ec07db424bc8dea36b393520514964439d5c1be3f85ca2a83b61983abd0	2026-11-03 11:13:32.384548-05	2026-11-03 12:13:32.624393-05	2026-11-03 11:25:29.813069-05
2	39	449ffefff428fb727967711ff2abbdb430fa08d26da81625b1e90036365a3f14	2026-11-03 11:25:40.348247-05	2026-11-03 12:25:40.580068-05	\N
3	39	2ccc3ad1500b14d076fc3c2685a74d3085f535510c6f070dfa8f645ff7c99f3d	2026-11-03 13:11:09.859764-05	2026-11-03 14:11:10.110196-05	2026-11-03 13:14:23.903499-05
4	2	1f34e0e4b9f81c40dcccc9cdf373fda2a989fe6f88194e438d781b6842b73233	2026-11-03 13:14:32.11584-05	2026-11-03 14:14:32.353558-05	2026-11-03 13:56:03.171162-05
5	39	51b0748c343ecadc4e59cd1d58b3bab46a78dd7ae1eb7265687610092020c91d	2026-11-03 13:56:15.706543-05	2026-11-03 14:56:16.059595-05	2026-11-03 14:28:32.469333-05
6	2	e0cbd75ca0281428f2a43e9bfe71e16d954995758b1609a2540b00a889ef7630	2026-11-03 14:39:38.402077-05	2026-11-03 15:39:38.658539-05	2026-11-03 14:49:23.67427-05
7	39	0ab151547d98c48ac1eb2d8341bc1ab9226633e8b21509aaf0239fe5a596a9f6	2026-11-03 14:49:55.754222-05	2026-11-03 15:49:55.997087-05	2026-11-03 14:51:01.003188-05
\.


--
-- TOC entry 5170 (class 0 OID 16586)
-- Dependencies: 221
-- Data for Name: vehiculo; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.vehiculo (id, placa, color, modelo, marca, tipo, cliente_id) FROM stdin;
1	ABC123	NEGRA	2025	CRYPTON	MOTO	\N
86	M166	negro	2026	Mazda	AUTOMOVIL	221
371	M165	negro	2025	navi	MOTO	221
420	M167	blanco	2026	mazda	AUTOMOVIL	266
\.


--
-- TOC entry 5195 (class 0 OID 0)
-- Dependencies: 230
-- Name: auditoria_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.auditoria_id_seq', 567, true);


--
-- TOC entry 5196 (class 0 OID 0)
-- Dependencies: 222
-- Name: celda_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.celda_id_seq', 10701, true);


--
-- TOC entry 5197 (class 0 OID 0)
-- Dependencies: 232
-- Name: cliente_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cliente_id_seq', 266, true);


--
-- TOC entry 5198 (class 0 OID 0)
-- Dependencies: 226
-- Name: estancia_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.estancia_id_seq', 210, true);


--
-- TOC entry 5199 (class 0 OID 0)
-- Dependencies: 236
-- Name: estancia_reasignacion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.estancia_reasignacion_id_seq', 19, true);


--
-- TOC entry 5200 (class 0 OID 0)
-- Dependencies: 224
-- Name: operador_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.operador_id_seq', 364, true);


--
-- TOC entry 5201 (class 0 OID 0)
-- Dependencies: 234
-- Name: puerta_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.puerta_id_seq', 264, true);


--
-- TOC entry 5202 (class 0 OID 0)
-- Dependencies: 228
-- Name: registro_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.registro_id_seq', 1, false);


--
-- TOC entry 5203 (class 0 OID 0)
-- Dependencies: 238
-- Name: sesion_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.sesion_id_seq', 7, true);


--
-- TOC entry 5204 (class 0 OID 0)
-- Dependencies: 220
-- Name: vehiculo_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.vehiculo_id_seq', 420, true);


--
-- TOC entry 4953 (class 2606 OID 16584)
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- TOC entry 4984 (class 2606 OID 16736)
-- Name: auditoria auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_pkey PRIMARY KEY (id);


--
-- TOC entry 4961 (class 2606 OID 16620)
-- Name: celda celda_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.celda
    ADD CONSTRAINT celda_pkey PRIMARY KEY (id);


--
-- TOC entry 4988 (class 2606 OID 16765)
-- Name: cliente cliente_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT cliente_pkey PRIMARY KEY (id);


--
-- TOC entry 4969 (class 2606 OID 16649)
-- Name: estancia estancia_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT estancia_pkey PRIMARY KEY (id);


--
-- TOC entry 4996 (class 2606 OID 16814)
-- Name: estancia_reasignacion estancia_reasignacion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia_reasignacion
    ADD CONSTRAINT estancia_reasignacion_pkey PRIMARY KEY (id);


--
-- TOC entry 4965 (class 2606 OID 16635)
-- Name: operador operador_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.operador
    ADD CONSTRAINT operador_pkey PRIMARY KEY (id);


--
-- TOC entry 4992 (class 2606 OID 16796)
-- Name: puerta puerta_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puerta
    ADD CONSTRAINT puerta_pkey PRIMARY KEY (id);


--
-- TOC entry 4982 (class 2606 OID 16690)
-- Name: registro registro_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_pkey PRIMARY KEY (id);


--
-- TOC entry 5002 (class 2606 OID 16865)
-- Name: sesion sesion_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT sesion_pkey PRIMARY KEY (id);


--
-- TOC entry 4963 (class 2606 OID 16622)
-- Name: celda uq_celda_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.celda
    ADD CONSTRAINT uq_celda_codigo UNIQUE (codigo);


--
-- TOC entry 4990 (class 2606 OID 16767)
-- Name: cliente uq_cliente_documento; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.cliente
    ADD CONSTRAINT uq_cliente_documento UNIQUE (documento);


--
-- TOC entry 4978 (class 2606 OID 16777)
-- Name: estancia uq_estancia_ficho_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT uq_estancia_ficho_codigo UNIQUE (ficho_codigo);


--
-- TOC entry 4967 (class 2606 OID 16715)
-- Name: operador uq_operador_usuario; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.operador
    ADD CONSTRAINT uq_operador_usuario UNIQUE (usuario);


--
-- TOC entry 4994 (class 2606 OID 16798)
-- Name: puerta uq_puerta_codigo; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.puerta
    ADD CONSTRAINT uq_puerta_codigo UNIQUE (codigo);


--
-- TOC entry 5004 (class 2606 OID 16867)
-- Name: sesion uq_sesion_token_hash; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT uq_sesion_token_hash UNIQUE (token_hash);


--
-- TOC entry 4957 (class 2606 OID 16606)
-- Name: vehiculo uq_vehiculo_placa; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT uq_vehiculo_placa UNIQUE (placa);


--
-- TOC entry 4959 (class 2606 OID 16604)
-- Name: vehiculo vehiculo_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT vehiculo_pkey PRIMARY KEY (id);


--
-- TOC entry 4980 (class 1259 OID 16707)
-- Name: idx_registro_estado; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_registro_estado ON public.registro USING btree (estado);


--
-- TOC entry 4954 (class 1259 OID 16706)
-- Name: idx_vehiculo_placa; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_vehiculo_placa ON public.vehiculo USING btree (placa);


--
-- TOC entry 4985 (class 1259 OID 16743)
-- Name: ix_auditoria_entidad_fecha; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_auditoria_entidad_fecha ON public.auditoria USING btree (entidad, entidad_id, fecha);


--
-- TOC entry 4986 (class 1259 OID 16742)
-- Name: ix_auditoria_operador_fecha; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_auditoria_operador_fecha ON public.auditoria USING btree (operador_id, fecha);


--
-- TOC entry 4970 (class 1259 OID 16877)
-- Name: ix_estancia_abierta_entrada; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_abierta_entrada ON public.estancia USING btree (entrada) WHERE (salida IS NULL);


--
-- TOC entry 4971 (class 1259 OID 16875)
-- Name: ix_estancia_entrada; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_entrada ON public.estancia USING btree (entrada);


--
-- TOC entry 4972 (class 1259 OID 16847)
-- Name: ix_estancia_puerta_entrada; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_puerta_entrada ON public.estancia USING btree (puerta_entrada_id);


--
-- TOC entry 4973 (class 1259 OID 16848)
-- Name: ix_estancia_puerta_salida; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_puerta_salida ON public.estancia USING btree (puerta_salida_id);


--
-- TOC entry 4974 (class 1259 OID 16876)
-- Name: ix_estancia_salida; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_salida ON public.estancia USING btree (salida) WHERE (salida IS NOT NULL);


--
-- TOC entry 4975 (class 1259 OID 16672)
-- Name: ix_estancia_vehiculo_entrada; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_estancia_vehiculo_entrada ON public.estancia USING btree (vehiculo_id, entrada);


--
-- TOC entry 4997 (class 1259 OID 16835)
-- Name: ix_reasignacion_estancia_fecha; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_reasignacion_estancia_fecha ON public.estancia_reasignacion USING btree (estancia_id, fecha);


--
-- TOC entry 4998 (class 1259 OID 16836)
-- Name: ix_reasignacion_operador; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_reasignacion_operador ON public.estancia_reasignacion USING btree (operador_id);


--
-- TOC entry 4999 (class 1259 OID 16873)
-- Name: ix_sesion_operador_creada; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_sesion_operador_creada ON public.sesion USING btree (operador_id, creada_en);


--
-- TOC entry 5000 (class 1259 OID 16874)
-- Name: ix_sesion_vigente; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_sesion_vigente ON public.sesion USING btree (expira_en) WHERE (revocada_en IS NULL);


--
-- TOC entry 4955 (class 1259 OID 16773)
-- Name: ix_vehiculo_cliente; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_vehiculo_cliente ON public.vehiculo USING btree (cliente_id);


--
-- TOC entry 4976 (class 1259 OID 16671)
-- Name: uq_estancia_celda_abierta; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_estancia_celda_abierta ON public.estancia USING btree (celda_id) WHERE (salida IS NULL);


--
-- TOC entry 4979 (class 1259 OID 16670)
-- Name: uq_estancia_vehiculo_abierta; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_estancia_vehiculo_abierta ON public.estancia USING btree (vehiculo_id) WHERE (salida IS NULL);


--
-- TOC entry 5015 (class 2606 OID 16737)
-- Name: auditoria fk_auditoria_operador; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT fk_auditoria_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5006 (class 2606 OID 16655)
-- Name: estancia fk_estancia_celda; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_celda FOREIGN KEY (celda_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- TOC entry 5007 (class 2606 OID 16660)
-- Name: estancia fk_estancia_operador_entrada; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_operador_entrada FOREIGN KEY (operador_entrada_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5008 (class 2606 OID 16665)
-- Name: estancia fk_estancia_operador_salida; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_operador_salida FOREIGN KEY (operador_salida_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5009 (class 2606 OID 16837)
-- Name: estancia fk_estancia_puerta_entrada; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_puerta_entrada FOREIGN KEY (puerta_entrada_id) REFERENCES public.puerta(id) ON DELETE RESTRICT;


--
-- TOC entry 5010 (class 2606 OID 16842)
-- Name: estancia fk_estancia_puerta_salida; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_puerta_salida FOREIGN KEY (puerta_salida_id) REFERENCES public.puerta(id) ON DELETE RESTRICT;


--
-- TOC entry 5011 (class 2606 OID 16650)
-- Name: estancia fk_estancia_vehiculo; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia
    ADD CONSTRAINT fk_estancia_vehiculo FOREIGN KEY (vehiculo_id) REFERENCES public.vehiculo(id) ON DELETE RESTRICT;


--
-- TOC entry 5016 (class 2606 OID 16820)
-- Name: estancia_reasignacion fk_reasignacion_celda_anterior; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia_reasignacion
    ADD CONSTRAINT fk_reasignacion_celda_anterior FOREIGN KEY (celda_anterior_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- TOC entry 5017 (class 2606 OID 16825)
-- Name: estancia_reasignacion fk_reasignacion_celda_nueva; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia_reasignacion
    ADD CONSTRAINT fk_reasignacion_celda_nueva FOREIGN KEY (celda_nueva_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- TOC entry 5018 (class 2606 OID 16815)
-- Name: estancia_reasignacion fk_reasignacion_estancia; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia_reasignacion
    ADD CONSTRAINT fk_reasignacion_estancia FOREIGN KEY (estancia_id) REFERENCES public.estancia(id) ON DELETE RESTRICT;


--
-- TOC entry 5019 (class 2606 OID 16830)
-- Name: estancia_reasignacion fk_reasignacion_operador; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.estancia_reasignacion
    ADD CONSTRAINT fk_reasignacion_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5020 (class 2606 OID 16868)
-- Name: sesion fk_sesion_operador; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sesion
    ADD CONSTRAINT fk_sesion_operador FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5005 (class 2606 OID 16768)
-- Name: vehiculo fk_vehiculo_cliente; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.vehiculo
    ADD CONSTRAINT fk_vehiculo_cliente FOREIGN KEY (cliente_id) REFERENCES public.cliente(id) ON DELETE RESTRICT;


--
-- TOC entry 5012 (class 2606 OID 16696)
-- Name: registro registro_celda_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_celda_id_fkey FOREIGN KEY (celda_id) REFERENCES public.celda(id) ON DELETE RESTRICT;


--
-- TOC entry 5013 (class 2606 OID 16701)
-- Name: registro registro_operador_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_operador_id_fkey FOREIGN KEY (operador_id) REFERENCES public.operador(id) ON DELETE RESTRICT;


--
-- TOC entry 5014 (class 2606 OID 16691)
-- Name: registro registro_vehiculo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.registro
    ADD CONSTRAINT registro_vehiculo_id_fkey FOREIGN KEY (vehiculo_id) REFERENCES public.vehiculo(id) ON DELETE RESTRICT;


-- Completed on 2026-11-03 15:06:35

--
-- PostgreSQL database dump complete
--

\unrestrict J4VEFfgxYo6r52t2UAlTDxY88BBmqDbSkYfFwmtYBRXAlzVMulbEjaTWWFk4U77

