--
-- PostgreSQL database dump
--

\restrict uyverYDfbFESJ5aZzapKUknJmEbXyCc1444ENOlR2kSbfaYiCe45ovmWF5k1K7e

-- Dumped from database version 14.20 (Ubuntu 14.20-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.20 (Ubuntu 14.20-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
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
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    user_id integer,
    action character varying(200) NOT NULL,
    meta character varying(1000),
    created_at timestamp without time zone
);


ALTER TABLE public.audit_log OWNER TO postgres;

--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.audit_log_id_seq OWNER TO postgres;

--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: landlord_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.landlord_settings (
    id integer NOT NULL,
    user_id integer NOT NULL,
    payment_method character varying(50),
    paybill_number character varying(32),
    till_number character varying(32),
    send_money_number character varying(32),
    phone_number character varying(50),
    created_at timestamp without time zone,
    updated_at timestamp without time zone,
    mpesa_consumer_key character varying(255),
    mpesa_consumer_secret character varying(255),
    mpesa_shortcode character varying(32),
    mpesa_passkey character varying(255),
    mpesa_mode character varying(20) DEFAULT 'production'::character varying NOT NULL,
    callback_url character varying(512)
);


ALTER TABLE public.landlord_settings OWNER TO postgres;

--
-- Name: landlord_settings_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.landlord_settings_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.landlord_settings_id_seq OWNER TO postgres;

--
-- Name: landlord_settings_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.landlord_settings_id_seq OWNED BY public.landlord_settings.id;


--
-- Name: mpesa_credential; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.mpesa_credential (
    id integer NOT NULL,
    user_id integer NOT NULL,
    shortcode character varying(50),
    shortcode_type character varying(20),
    callback_url character varying(500),
    mpesa_env character varying(20),
    encrypted_consumer_key bytea,
    encrypted_consumer_secret bytea,
    encrypted_passkey bytea
);


ALTER TABLE public.mpesa_credential OWNER TO postgres;

--
-- Name: mpesa_credential_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.mpesa_credential_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.mpesa_credential_id_seq OWNER TO postgres;

--
-- Name: mpesa_credential_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.mpesa_credential_id_seq OWNED BY public.mpesa_credential.id;


--
-- Name: payment; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.payment (
    id integer NOT NULL,
    transaction_id character varying(100) NOT NULL,
    amount double precision NOT NULL,
    paid_at timestamp without time zone NOT NULL,
    created_at timestamp without time zone,
    note character varying(255),
    tenant_id integer,
    user_id integer,
    checkout_request_id character varying(100)
);


ALTER TABLE public.payment OWNER TO postgres;

--
-- Name: payment_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.payment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.payment_id_seq OWNER TO postgres;

--
-- Name: payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.payment_id_seq OWNED BY public.payment.id;


--
-- Name: tenant; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tenant (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    name character varying(180) NOT NULL,
    phone character varying(80) NOT NULL,
    national_id character varying(80),
    house_no character varying(80) NOT NULL,
    monthly_rent double precision NOT NULL,
    move_in_date date NOT NULL,
    created_at timestamp without time zone,
    last_rent_update date NOT NULL,
    amount_due double precision NOT NULL
);


ALTER TABLE public.tenant OWNER TO postgres;

--
-- Name: tenant_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tenant_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.tenant_id_seq OWNER TO postgres;

--
-- Name: tenant_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tenant_id_seq OWNED BY public.tenant.id;


--
-- Name: user; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    full_name character varying(180),
    email character varying(256) NOT NULL,
    login_phone character varying(20),
    password_hash character varying(256) NOT NULL,
    is_admin boolean,
    created_at timestamp without time zone,
    payment_method character varying(50),
    phone_number character varying(20),
    paybill_number character varying(30),
    till_number character varying(30),
    mpesa_consumer_key character varying(200),
    mpesa_consumer_secret character varying(200),
    mpesa_passkey character varying(200),
    mpesa_shortcode character varying(20),
    mpesa_env character varying(20),
    mpesa_callback_url character varying(500),
    reset_code character varying(10),
    reset_code_expires_at timestamp without time zone,
    last_logout timestamp without time zone
);


ALTER TABLE public."user" OWNER TO postgres;

--
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.user_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_id_seq OWNER TO postgres;

--
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: landlord_settings id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.landlord_settings ALTER COLUMN id SET DEFAULT nextval('public.landlord_settings_id_seq'::regclass);


--
-- Name: mpesa_credential id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mpesa_credential ALTER COLUMN id SET DEFAULT nextval('public.mpesa_credential_id_seq'::regclass);


--
-- Name: payment id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment ALTER COLUMN id SET DEFAULT nextval('public.payment_id_seq'::regclass);


--
-- Name: tenant id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tenant ALTER COLUMN id SET DEFAULT nextval('public.tenant_id_seq'::regclass);


--
-- Name: user id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: landlord_settings landlord_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.landlord_settings
    ADD CONSTRAINT landlord_settings_pkey PRIMARY KEY (id);


--
-- Name: mpesa_credential mpesa_credential_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mpesa_credential
    ADD CONSTRAINT mpesa_credential_pkey PRIMARY KEY (id);


--
-- Name: payment payment_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_pkey PRIMARY KEY (id);


--
-- Name: payment payment_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_transaction_id_key UNIQUE (transaction_id);


--
-- Name: tenant tenant_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tenant
    ADD CONSTRAINT tenant_pkey PRIMARY KEY (id);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: ix_landlord_settings_user_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_landlord_settings_user_id ON public.landlord_settings USING btree (user_id);


--
-- Name: ix_payment_checkout_request_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_payment_checkout_request_id ON public.payment USING btree (checkout_request_id);


--
-- Name: ix_user_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_user_email ON public."user" USING btree (email);


--
-- Name: ix_user_login_phone; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_user_login_phone ON public."user" USING btree (login_phone);


--
-- Name: audit_log audit_log_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: landlord_settings landlord_settings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.landlord_settings
    ADD CONSTRAINT landlord_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: mpesa_credential mpesa_credential_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.mpesa_credential
    ADD CONSTRAINT mpesa_credential_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: payment payment_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenant(id);


--
-- Name: payment payment_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payment
    ADD CONSTRAINT payment_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id);


--
-- Name: tenant tenant_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tenant
    ADD CONSTRAINT tenant_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public."user"(id);


--
-- PostgreSQL database dump complete
--

\unrestrict uyverYDfbFESJ5aZzapKUknJmEbXyCc1444ENOlR2kSbfaYiCe45ovmWF5k1K7e

