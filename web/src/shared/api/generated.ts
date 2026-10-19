// Generated from contracts/omnis.openapi.json. Do not edit.
export interface paths {
    "/api/instance": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Instance */
        get: operations["instance_api_instance_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/pairing": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Pair */
        post: operations["pair_api_pairing_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/session": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Session */
        get: operations["session_api_session_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Dashboard */
        get: operations["read_dashboard_api_v1_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/engagements": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Engagements */
        get: operations["list_engagements_api_v1_engagements_get"];
        put?: never;
        /** Create Engagement */
        post: operations["create_engagement_api_v1_engagements_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/engagements/{engagement_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Engagement */
        get: operations["read_engagement_api_v1_engagements__engagement_id__get"];
        /** Edit Engagement */
        put: operations["edit_engagement_api_v1_engagements__engagement_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/engagements/{engagement_id}/revisions": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Revisions */
        get: operations["list_revisions_api_v1_engagements__engagement_id__revisions_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Model Test */
        get: operations["read_model_test_api_v1_model_test_get"];
        /** Start Model Test */
        put: operations["start_model_test_api_v1_model_test_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/catalog": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Current */
        get: operations["current_api_v1_settings_catalog_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/catalog/page/{after}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Next Page */
        get: operations["next_page_api_v1_settings_catalog_page__after__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/catalog/publications/{publication_id}/{digest}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Detail */
        get: operations["detail_api_v1_settings_catalog_publications__publication_id___digest__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/provider": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Configure */
        put: operations["configure_api_v1_settings_provider_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/provider/operations/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Operation */
        get: operations["operation_api_v1_settings_provider_operations__operation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/live": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Live */
        get: operations["live_health_live_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/health/ready": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Ready */
        get: operations["ready_health_ready_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ApplicationContext */
        ApplicationContext: {
            /** Import Ref */
            import_ref: null;
            /** Priority Workflows */
            priority_workflows: string[];
            /** Seed Urls */
            seed_urls: string[];
            /** Test Objects */
            test_objects: string[];
        };
        /** @enum {string} */
        AssessmentMode: "FULL_ASSESSMENT" | "FOCUSED_TEST";
        /** Authorization */
        Authorization: {
            /** Owner */
            owner: string;
            /** Statement */
            statement: string;
            /** Valid From */
            valid_from: string;
            /** Valid Until */
            valid_until: string;
        };
        /** BusinessMatrixEntry */
        BusinessMatrixEntry: {
            expected: components["schemas"]["DeclaredDecision"];
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Object */
            object: string;
            /** Operation */
            operation: string;
            /** Principal */
            principal: string;
            /** Role */
            role: string;
            /** Source */
            source: string;
            /** Source Revision */
            source_revision: number;
            /** Tenant */
            tenant: string;
        };
        /** CatalogBinding */
        CatalogBinding: {
            /**
             * Entity Kind
             * @enum {string}
             */
            entity_kind: "package" | "profile" | "technique" | "procedure" | "schema" | "method" | "prompt" | "template" | "overlay" | "asset";
            /** Key */
            key: string;
            /** Package Key */
            package_key: string | "@profile";
            ref: components["schemas"]["CatalogPin"];
        };
        /** CatalogEntry */
        CatalogEntry: {
            /** Generation */
            generation: number;
            /** Profile Key */
            profile_key: string;
            publication_ref: components["schemas"]["CatalogPin"];
        };
        /** CatalogInspection */
        CatalogInspection: {
            /**
             * Assessment Selectable
             * @constant
             */
            assessment_selectable: false;
            /**
             * Benchmark
             * @constant
             */
            benchmark: "NOT_VERIFIED";
            /** Candidate Refs */
            candidate_refs: components["schemas"]["CatalogPin"][];
            /** Catalog Bindings */
            catalog_bindings: components["schemas"]["CatalogBinding"][];
            /** Compiler Revision */
            compiler_revision: string;
            confirmation_ref: components["schemas"]["CatalogPin"];
            /** Dependency Artifact Refs */
            dependency_artifact_refs: components["schemas"]["CatalogPin"][];
            /** Dependency Closure Digest */
            dependency_closure_digest: string;
            /** Dependency Closure Refs */
            dependency_closure_refs: components["schemas"]["CatalogPin"][];
            /**
             * Dependency Metadata
             * @enum {string}
             */
            dependency_metadata: "NO_EXTERNAL_DEPENDENCIES" | "NOT_VERIFIED";
            /** Evaluator Revision */
            evaluator_revision: string;
            /**
             * Fixture
             * @constant
             */
            fixture: "NOT_VERIFIED";
            /** Generation */
            generation: number;
            /**
             * Material
             * @constant
             */
            material: "NOT_VERIFIED";
            /** Material Digest */
            material_digest: string;
            /** Owner Id */
            owner_id: string;
            /** Profile Key */
            profile_key: string;
            profile_ref: components["schemas"]["CatalogPin"];
            publication_ref: components["schemas"]["CatalogPin"];
            /**
             * Pure
             * @constant
             */
            pure: "RECORDED_PURE_PASS";
            pure_evaluation_ref: components["schemas"]["CatalogPin"];
            requested: components["schemas"]["Preference"];
            /**
             * Resolution
             * @constant
             */
            resolution: "NO_MODEL";
            /** Resolved Index Digest */
            resolved_index_digest: string;
            /**
             * Review
             * @constant
             */
            review: "RECORDED_STATIC_PASS";
            /**
             * Runtime
             * @constant
             */
            runtime: "NOT_AVAILABLE";
            /**
             * Security
             * @constant
             */
            security: "NOT_VERIFIED";
            snapshot_ref: components["schemas"]["CatalogPin"];
            /** Source Draft Refs */
            source_draft_refs: components["schemas"]["CatalogPin"][];
            /**
             * Static
             * @constant
             */
            static: "RECORDED_STATIC_PASS";
            static_evaluation_ref: components["schemas"]["CatalogPin"];
            technical_review_ref: components["schemas"]["CatalogPin"];
        };
        /** CatalogPage */
        CatalogPage: {
            /** Has More */
            has_more: boolean;
            /** Items */
            items: components["schemas"]["CatalogEntry"][];
            /** Next After */
            next_after: string | null;
        };
        /** CatalogPin */
        CatalogPin: {
            /** Digest */
            digest: string;
            /** Id */
            id: string;
            /**
             * Kind
             * @enum {string}
             */
            kind: "source-draft" | "candidate-snapshot" | "technical-review" | "evaluation-receipt" | "operator-confirmation" | "catalog-publication" | "evaluation-input" | "contract-case-input" | "contract-case-records" | "contract-input-context" | "evaluation-admission" | "qualified-release" | "release-qualification" | "package" | "profile" | "technique" | "procedure" | "schema" | "method" | "prompt" | "template" | "overlay" | "asset";
            /** Revision */
            revision: number;
        };
        /** @enum {string} */
        ConstraintKind: "READ_ONLY" | "EXCLUDE_FEATURE" | "REQUIRE_CRITERION";
        /** DashboardData */
        DashboardData: {
            /** Active Run */
            active_run?: null;
            /**
             * Attention State
             * @default UNAVAILABLE
             * @constant
             */
            attention_state: "UNAVAILABLE";
            /** Items */
            items: components["schemas"]["DashboardEngagement"][];
            metrics?: components["schemas"]["DashboardMetrics"];
            /**
             * Run State
             * @default NOT_RUN
             * @constant
             */
            run_state: "NOT_RUN";
            /** Total Engagements */
            total_engagements: number;
        };
        /** DashboardEngagement */
        DashboardEngagement: {
            assessment_mode: components["schemas"]["AssessmentMode"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Digest */
            digest: string;
            /**
             * Engagement Id
             * Format: uuid
             */
            engagement_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
            /** Run Id */
            run_id?: null;
            /**
             * Run State
             * @default NOT_RUN
             * @constant
             */
            run_state: "NOT_RUN";
            /**
             * Scope Revision Id
             * Format: uuid
             */
            scope_revision_id: string;
            /**
             * Stage
             * @default NOT_RUN
             * @constant
             */
            stage: "NOT_RUN";
            /** Through Cursor */
            through_cursor?: null;
        };
        /** DashboardMetrics */
        DashboardMetrics: {
            confirmed?: components["schemas"]["RunMetric"];
            cost?: components["schemas"]["RunMetric"];
            coverage?: components["schemas"]["RunMetric"];
        };
        /**
         * DashboardReason
         * @enum {string}
         */
        DashboardReason: "ASSETS_UNAVAILABLE" | "CONTROL_UNAVAILABLE";
        /** @enum {string} */
        DeclaredDecision: "ALLOW" | "DENY" | "UNKNOWN";
        /** DraftBudgets */
        DraftBudgets: {
            /** Max Duration Seconds */
            max_duration_seconds: number;
            /** Max Model Calls */
            max_model_calls: number;
            /** Max Requests */
            max_requests: number;
            /** Max Storage Bytes */
            max_storage_bytes: number;
            /** Validation Reserved Requests */
            validation_reserved_requests: number;
        };
        /** DraftDataPolicy */
        DraftDataPolicy: {
            /**
             * Model Projection
             * @enum {string}
             */
            model_projection: "NONE" | "REDACTED";
            /**
             * Research Egress
             * @enum {string}
             */
            research_egress: "NONE" | "PUBLIC_FACTS";
            /** Retention Days */
            retention_days: number;
        };
        /** @enum {string} */
        EffectClass: "READ_ONLY_KNOWN" | "SESSION_CHANGE" | "LIMITED_WRITE" | "DESTRUCTIVE" | "UNKNOWN";
        /** EffectRule */
        EffectRule: {
            decision: components["schemas"]["DeclaredDecision"];
            effect_class: components["schemas"]["EffectClass"];
            /** Note */
            note: string;
        };
        /**
         * EngagementDraft
         * @description B02b authored payload. Legacy rows remain exactly readable, not backfilled.
         */
        EngagementDraft: {
            application_context: components["schemas"]["ApplicationContext"];
            assessment_mode: components["schemas"]["AssessmentMode"];
            authorization: components["schemas"]["Authorization"];
            budgets: components["schemas"]["DraftBudgets"];
            /** Business Matrix */
            business_matrix: components["schemas"]["BusinessMatrixEntry"][];
            /** Business Rules Ref */
            business_rules_ref: null;
            data_policy: components["schemas"]["DraftDataPolicy"];
            /** Effect Rules */
            effect_rules: components["schemas"]["EffectRule"][];
            /** Name */
            name: string;
            /** Objective Constraints */
            objective_constraints: components["schemas"]["ObjectiveConstraint"][];
            /** Objective Text */
            objective_text: string;
            /** Scope */
            scope: components["schemas"]["ScopeEntry"][];
            /** Workflow Profile Ref */
            workflow_profile_ref: null;
        };
        /** EngagementPage */
        EngagementPage: {
            /** Has More */
            has_more: boolean;
            /** Items */
            items: components["schemas"]["EngagementSummary"][];
            /** Next Page */
            next_page: string | null;
        };
        /** EngagementSummary */
        EngagementSummary: {
            assessment_mode: components["schemas"]["AssessmentMode"];
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Digest */
            digest: string;
            /**
             * Engagement Id
             * Format: uuid
             */
            engagement_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /** Name */
            name: string;
            /** Revision */
            revision: number;
        };
        /** EngagementView */
        EngagementView: {
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            /** Digest */
            digest: string;
            /**
             * Engagement Id
             * Format: uuid
             */
            engagement_id: string;
            /**
             * Id
             * Format: uuid
             */
            id: string;
            /**
             * Kind
             * @constant
             */
            kind: "engagement-revision";
            /** Payload */
            payload: components["schemas"]["LegacyEngagementDraft"] | components["schemas"]["EngagementDraft"];
            /** Revision */
            revision: number;
            /**
             * Schema Version
             * @constant
             */
            schema_version: 1;
        };
        /**
         * ErrorCode
         * @enum {string}
         */
        ErrorCode: "INVALID_HOST" | "INVALID_ORIGIN" | "QUERY_NOT_ALLOWED" | "BODY_TOO_LARGE" | "UNAUTHENTICATED" | "CONTROL_UNAVAILABLE" | "INVALID_CSRF" | "CONTROL_TIMEOUT" | "PAIRING_DENIED" | "PAIRING_RATE_LIMITED" | "INVALID_INPUT" | "ENGAGEMENT_CONFLICT" | "NOT_FOUND" | "METHOD_NOT_ALLOWED" | "HTTP_ERROR" | "INTERNAL_ERROR" | "WEB_UNAVAILABLE";
        /** ErrorDetail */
        ErrorDetail: {
            code: components["schemas"]["ErrorCode"];
            /**
             * Correlation Id
             * Format: uuid
             */
            correlation_id: string;
            /** Field Errors */
            field_errors?: components["schemas"]["FieldError"][];
        };
        /** ErrorEnvelope */
        ErrorEnvelope: {
            error: components["schemas"]["ErrorDetail"];
        };
        /** FieldError */
        FieldError: {
            /**
             * Code
             * @enum {string}
             */
            code: "REQUIRED" | "INVALID_VALUE" | "TOO_LONG" | "TOO_MANY" | "UNKNOWN_FIELD";
            /** Field */
            field: string;
        };
        /** HealthReady */
        HealthReady: {
            /** Api Ready */
            api_ready: boolean;
            /** Assessment Ready */
            assessment_ready: boolean;
            /** Dashboard Ready */
            dashboard_ready: boolean;
            /** Dashboard Reason */
            dashboard_reason: components["schemas"]["ReadinessReason"] | components["schemas"]["DashboardReason"] | null;
            reason: components["schemas"]["ReadinessReason"] | null;
        };
        /** InstanceView */
        InstanceView: {
            /** Admission Open */
            admission_open: boolean;
            /** Assessment Ready */
            assessment_ready: boolean;
            /** Dashboard Ready */
            dashboard_ready: boolean;
            /** Generation */
            generation: number;
            /**
             * Instance Id
             * Format: uuid
             */
            instance_id: string;
            /** Quiesced Generation */
            quiesced_generation: number | null;
            /** Shutdown Command Id */
            shutdown_command_id: string | null;
            /** Shutdown Finalized */
            shutdown_finalized: boolean;
            /** Supervisor Epoch */
            supervisor_epoch: number;
            /** Supervisor Ready */
            supervisor_ready: boolean;
        };
        /** LegacyEngagementDraft */
        LegacyEngagementDraft: {
            assessment_mode: components["schemas"]["AssessmentMode"];
            authorization: components["schemas"]["Authorization"];
            /** Name */
            name: string;
            /** Objective Constraints */
            objective_constraints: components["schemas"]["ObjectiveConstraint"][];
            /** Objective Text */
            objective_text: string;
            /** Scope */
            scope: components["schemas"]["ScopeEntry"][];
            /** Workflow Profile Ref */
            workflow_profile_ref: null;
        };
        /** ModelTestRequest */
        ModelTestRequest: {
            /**
             * Consent
             * @constant
             */
            consent: true;
            /** Operation Id */
            operation_id: string;
        };
        /** ModelTestView */
        ModelTestView: {
            /**
             * Calls Limit
             * @default 1
             * @constant
             */
            calls_limit: 1;
            /** Duration Ms */
            duration_ms?: number | null;
            /** Input Tokens */
            input_tokens?: number | null;
            /** Observed Effort */
            observed_effort?: string | null;
            /** Observed Model */
            observed_model?: string | null;
            /** Operation Id */
            operation_id: string | null;
            /** Output Tokens */
            output_tokens?: number | null;
            /** Reason */
            reason: string | null;
            /** Reasoning Tokens */
            reasoning_tokens?: number | null;
            /**
             * Requested Effort
             * @default xhigh
             * @constant
             */
            requested_effort: "xhigh";
            /**
             * Requested Model
             * @default gpt-6.1-sol
             * @constant
             */
            requested_model: "gpt-6.1-sol";
            /**
             * Requested Provider
             * @default openai-codex
             * @constant
             */
            requested_provider: "openai-codex";
            /** Response Text */
            response_text?: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "AVAILABLE" | "UNAVAILABLE" | "PENDING" | "COMPLETE" | "UNKNOWN" | "ERROR";
            /** System Message */
            system_message: string;
            /** User Message */
            user_message: string;
            /**
             * Wall Seconds
             * @default 300
             * @constant
             */
            wall_seconds: 300;
        };
        /** OAuthChallenge */
        OAuthChallenge: {
            /** Code */
            code: string;
            /**
             * Url
             * @constant
             */
            url: "https://auth.openai.com/codex/device";
        };
        /** ObjectiveConstraint */
        ObjectiveConstraint: {
            /**
             * Id
             * Format: uuid
             */
            id: string;
            kind: components["schemas"]["ConstraintKind"];
            /** Operation Refs */
            operation_refs: unknown[];
            /** Text */
            text: string;
        };
        /** PairingBody */
        PairingBody: {
            /** Code */
            code: string;
        };
        /** Preference */
        Preference: {
            /** Effort */
            effort: string | null;
            /** Model Key */
            model_key: string | null;
            /**
             * On Unavailable
             * @enum {string}
             */
            on_unavailable: "BLOCK" | "USE_RUN_DEFAULT";
            /**
             * Requirement
             * @enum {string}
             */
            requirement: "REQUIRED" | "PREFERRED";
        };
        /** ProjectionEnvelope */
        ProjectionEnvelope: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /**
             * Context
             * @default GLOBAL
             * @constant
             */
            context: "GLOBAL";
            data: components["schemas"]["DashboardData"];
            /**
             * Data State
             * @default AVAILABLE
             * @constant
             */
            data_state: "AVAILABLE";
            /** Engagement Id */
            engagement_id?: null;
            /** Has More */
            has_more: boolean;
            /** Limit */
            limit: number;
            /** Next Page */
            next_page?: string | null;
            /** Run Id */
            run_id?: null;
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
            /** Scope Revision Id */
            scope_revision_id?: null;
            /** Through Cursor */
            through_cursor?: null;
        };
        /** ProviderCommand */
        ProviderCommand: {
            /**
             * Action
             * @enum {string}
             */
            action: "read" | "save" | "auth_read" | "logout" | "connect" | "cancel";
            /** Operation Id */
            operation_id: string;
            selection: components["schemas"]["ProviderSelection"] | null;
        };
        /** ProviderSelection */
        ProviderSelection: {
            /**
             * Effort
             * @constant
             */
            effort: "xhigh";
            /**
             * Model
             * @constant
             */
            model: "gpt-6.1-sol";
            /**
             * Provider
             * @constant
             */
            provider: "openai-codex";
        };
        /** ProviderView */
        ProviderView: {
            /**
             * Authenticated
             * @enum {string}
             */
            authenticated: "NOT_VERIFIED" | "ABSENT" | "LOCAL_PRESENT" | "LOCAL_EXPIRED" | "LOCAL_UNKNOWN";
            challenge?: components["schemas"]["OAuthChallenge"] | null;
            /** Configured */
            configured: boolean;
            /**
             * Inference Ready
             * @constant
             */
            inference_ready: false;
            /**
             * Oauth
             * @default NONE
             * @enum {string}
             */
            oauth: "NONE" | "STARTING" | "CHALLENGE" | "CANCELLING" | "CANCELLED" | "EXPIRED" | "SAVED" | "INDETERMINATE";
            /** Operation Id */
            operation_id: string;
            /**
             * Reachable
             * @constant
             */
            reachable: "NOT_VERIFIED";
            selection: components["schemas"]["ProviderSelection"] | null;
            /**
             * Status
             * @enum {string}
             */
            status: "PENDING" | "CONFIRMED" | "INDETERMINATE" | "BUSY" | "UNAVAILABLE";
        };
        /**
         * ReadinessReason
         * @enum {string}
         */
        ReadinessReason: "DATABASE_UNAVAILABLE" | "SCHEMA_INCOMPATIBLE";
        /** RevisionPage */
        RevisionPage: {
            /** Has More */
            has_more: boolean;
            /** Items */
            items: components["schemas"]["EngagementView"][];
            /** Next Page */
            next_page: number | null;
        };
        /** RunMetric */
        RunMetric: {
            /**
             * Reason
             * @default NOT_RUN
             * @constant
             */
            reason: "NOT_RUN";
            /**
             * State
             * @default UNAVAILABLE
             * @constant
             */
            state: "UNAVAILABLE";
            /** Value */
            value?: null;
        };
        /** @enum {string} */
        ScopeAccess: "ATTACKABLE" | "VISIT_ONLY" | "BLOCKED";
        /** ScopeEntry */
        ScopeEntry: {
            access: components["schemas"]["ScopeAccess"];
            /** Exclusions */
            exclusions: string[];
            /** Origin */
            origin: string;
            /** Path Prefix */
            path_prefix: string;
            /** Port */
            port: number;
        };
        /** SessionView */
        SessionView: {
            /**
             * Authenticated
             * @default true
             */
            authenticated: boolean;
            /** Csrf Token */
            csrf_token: string;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    instance_api_instance_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstanceView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    logout_api_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    pair_api_pairing_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["PairingBody"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Too Many Requests */
            429: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    session_api_session_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SessionView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    read_dashboard_api_v1_dashboard_get: {
        parameters: {
            query?: {
                limit?: number;
                after?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectionEnvelope"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    list_engagements_api_v1_engagements_get: {
        parameters: {
            query?: {
                limit?: number;
                after?: string | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngagementPage"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    create_engagement_api_v1_engagements_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EngagementDraft"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngagementView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    read_engagement_api_v1_engagements__engagement_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                engagement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngagementView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    edit_engagement_api_v1_engagements__engagement_id__put: {
        parameters: {
            query?: never;
            header: {
                /** @description Exact strong ETag: "rev-<positive decimal revision>-<64 lowercase hex digest>" */
                "if-match": string;
                /** @description Explicit canonical lowercase UUID, unique per engagement edit command */
                "x-command-id": string;
            };
            path: {
                engagement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EngagementDraft"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EngagementView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Conflict */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    list_revisions_api_v1_engagements__engagement_id__revisions_get: {
        parameters: {
            query?: {
                limit?: number;
                after?: number | null;
            };
            header?: never;
            path: {
                engagement_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RevisionPage"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    read_model_test_api_v1_model_test_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelTestView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    start_model_test_api_v1_model_test_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ModelTestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelTestView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Not Found */
            404: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    current_api_v1_settings_catalog_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogPage"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    next_page_api_v1_settings_catalog_page__after__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                after: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogPage"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    detail_api_v1_settings_catalog_publications__publication_id___digest__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                publication_id: string;
                digest: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogInspection"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    configure_api_v1_settings_provider_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProviderCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Content Too Large */
            413: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    operation_api_v1_settings_provider_operations__operation_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProviderView"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unauthorized */
            401: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Unprocessable Content */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Service Unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    live_health_live_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": {
                        [key: string]: string;
                    };
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
        };
    };
    ready_health_ready_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthReady"];
                };
            };
            /** @description Bad Request */
            400: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Forbidden */
            403: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Internal Server Error */
            500: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ErrorEnvelope"];
                };
            };
            /** @description Database or schema unavailable */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthReady"];
                };
            };
        };
    };
}
