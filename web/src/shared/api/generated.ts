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
    "/api/v1/engagements/{engagement_id}/run": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Engagement Run */
        get: operations["engagement_run_api_v1_engagements__engagement_id__run_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/engagements/{engagement_id}/run-preflight": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Preflight */
        post: operations["preflight_api_v1_engagements__engagement_id__run_preflight_post"];
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
    "/api/v1/model-test/capabilities": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh Capabilities */
        post: operations["refresh_capabilities_api_v1_model_test_capabilities_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/capabilities/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Capabilities */
        get: operations["read_capabilities_api_v1_model_test_capabilities__command_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/entries": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        /** Start Entry Test */
        put: operations["start_entry_test_api_v1_model_test_entries_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/entries/latest/{entry_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Latest Entry Test */
        get: operations["read_latest_entry_test_api_v1_model_test_entries_latest__entry_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/entries/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Entry Test */
        get: operations["read_entry_test_api_v1_model_test_entries__operation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/entries/{operation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Entry Test */
        post: operations["cancel_entry_test_api_v1_model_test_entries__operation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/{operation_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Operation */
        get: operations["read_operation_api_v1_model_test__operation_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/model-test/{operation_id}/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Operation */
        post: operations["cancel_operation_api_v1_model_test__operation_id__cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Start */
        post: operations["start_api_v1_runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/active": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Active */
        get: operations["active_api_v1_runs_active_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/commands/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Command Read */
        get: operations["command_read_api_v1_runs_commands__command_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/publications": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Publications */
        get: operations["publications_api_v1_runs_publications_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/attempts/{attempt_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Attempt */
        get: operations["attempt_api_v1_runs__run_id__attempts__attempt_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/commands": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Command */
        post: operations["command_api_v1_runs__run_id__commands_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/events": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Events */
        get: operations["events_api_v1_runs__run_id__events_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/summary": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Summary */
        get: operations["summary_api_v1_runs__run_id__summary_get"];
        put?: never;
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
    "/api/v1/settings/models": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Models */
        get: operations["read_models_api_v1_settings_models_get"];
        /** Save Models */
        put: operations["save_models_api_v1_settings_models_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/models/commands/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Command */
        get: operations["read_command_api_v1_settings_models_commands__command_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/models/pages/{registry_revision}/{after}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Page */
        get: operations["read_page_api_v1_settings_models_pages__registry_revision___after__get"];
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
    "/api/v1/settings/provider-catalog/cancel": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Cancel Catalog */
        post: operations["cancel_catalog_api_v1_settings_provider_catalog_cancel_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/provider-catalog/refresh": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Refresh Catalog */
        post: operations["refresh_catalog_api_v1_settings_provider_catalog_refresh_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/provider-catalog/search": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Search Catalog */
        post: operations["search_catalog_api_v1_settings_provider_catalog_search_post"];
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
    "/api/v1/settings/providers": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Settings */
        get: operations["read_settings_api_v1_settings_providers_get"];
        /** Save Settings */
        put: operations["save_settings_api_v1_settings_providers_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/settings/providers/commands/{command_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Read Command */
        get: operations["read_command_api_v1_settings_providers_commands__command_id__get"];
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
        /** Attempt */
        Attempt: {
            attempt_id: components["schemas"]["Identity"];
            /** Brief */
            brief: string;
            /** Call Id */
            call_id?: string | null;
            /** Configured Model */
            configured_model: string;
            /**
             * Correction Count
             * @default 0
             */
            correction_count: number;
            /** Input Refs */
            input_refs: components["schemas"]["RunRef"][];
            /** Input Text */
            input_text: string;
            instance_id: components["schemas"]["Identity"];
            /** Instructions */
            instructions: string;
            /** Observed Model */
            observed_model?: string | null;
            parent_task_id: components["schemas"]["Identity"] | null;
            read_receipt_ref?: components["schemas"]["RunRef"] | null;
            result_ref?: components["schemas"]["RunRef"] | null;
            /** Result Summary */
            result_summary?: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "BRAIN" | "RECON";
            run_id: components["schemas"]["Identity"];
            /** Skill Refs */
            skill_refs: components["schemas"]["ExactRef"][];
            /**
             * State
             * @enum {string}
             */
            state: "RUNNING" | "SUCCEEDED" | "INCONCLUSIVE" | "FAILED" | "CANCELLED" | "NEEDS_RECONCILIATION";
            task_id: components["schemas"]["Identity"];
            /** Tool Arguments */
            tool_arguments?: string | null;
            /** Tool Output */
            tool_output?: string | null;
        };
        /** AttemptInspection */
        AttemptInspection: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            attempt_id: components["schemas"]["Identity"];
            /** Brief */
            brief: string;
            /** Call Id */
            call_id?: string | null;
            /** Configured Model */
            configured_model: string;
            consumption?: components["schemas"]["InboxConsumption"] | null;
            /**
             * Correction Count
             * @default 0
             */
            correction_count: number;
            decision?: components["schemas"]["BrainDecision"] | null;
            /** Decision Completion Kind */
            decision_completion_kind?: "direct" | null;
            /** Dispatches */
            dispatches?: components["schemas"]["DispatchUsage"][];
            /**
             * Dispatches Has More
             * @default false
             */
            dispatches_has_more: boolean;
            /** Input Refs */
            input_refs: components["schemas"]["RunRef"][];
            /** Input Text */
            input_text: string;
            instance_id: components["schemas"]["Identity"];
            /** Instructions */
            instructions: string;
            /** Observed Model */
            observed_model?: string | null;
            parent_task_id: components["schemas"]["Identity"] | null;
            read_receipt_ref?: components["schemas"]["RunRef"] | null;
            result?: components["schemas"]["ResultRecord"] | null;
            result_ref?: components["schemas"]["RunRef"] | null;
            /** Result Summary */
            result_summary?: string | null;
            /**
             * Role
             * @enum {string}
             */
            role: "BRAIN" | "RECON";
            run_id: components["schemas"]["Identity"];
            /** Skill Refs */
            skill_refs: components["schemas"]["ExactRef"][];
            /**
             * State
             * @enum {string}
             */
            state: "RUNNING" | "SUCCEEDED" | "INCONCLUSIVE" | "FAILED" | "CANCELLED" | "NEEDS_RECONCILIATION";
            task_id: components["schemas"]["Identity"];
            /** Tool Arguments */
            tool_arguments?: string | null;
            /** Tool Output */
            tool_output?: string | null;
            usage?: components["schemas"]["UsageSummary"] | null;
        };
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
        /** BrainDecision */
        BrainDecision: {
            /**
             * Action
             * @enum {string}
             */
            action: "delegate" | "ask" | "finish";
            /** Consumed Refs */
            consumed_refs: components["schemas"]["RunRef"][];
            /** Detail */
            detail: string;
            /** Summary */
            summary: string;
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
        /** CancelCatalog */
        CancelCatalog: {
            /**
             * Action
             * @constant
             */
            action: "cancel";
            catalog_command_id: components["schemas"]["Identity"];
            command_id: components["schemas"]["Identity"];
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
        };
        /** CancelTestRequest */
        CancelTestRequest: {
            command_id: components["schemas"]["Identity"];
            expected_state_revision: components["schemas"]["PositiveRevision"];
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
        /** CatalogModel */
        CatalogModel: {
            /** Max Output Tokens */
            max_output_tokens?: number | null;
            /** Model */
            model: string;
            /** Name */
            name?: string | null;
            reason?: components["schemas"]["CatalogReason"] | null;
            /** Supports Max Tokens */
            supports_max_tokens?: boolean | null;
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
        CatalogReason: "SCHEMA_UNSUPPORTED" | "CONTINUATION_UNSUPPORTED" | "TOTAL_MISMATCH" | "CATALOG_LIMIT" | "METADATA_UNAVAILABLE" | "CANCELLED_OR_STOPPED" | "OWNER_LOST" | "CONNECTION_STALE" | "ROW_UNSUPPORTED";
        /** CatalogView */
        CatalogView: {
            catalog_command_id: components["schemas"]["Identity"] | null;
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            /** Entries */
            entries: components["schemas"]["CatalogModel"][];
            /** Next Offset */
            next_offset?: number | null;
            /** Offset */
            offset: number;
            provider: components["schemas"]["Provider"];
            /** Query */
            query: string;
            reason?: components["schemas"]["CatalogReason"] | null;
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
            /**
             * State
             * @enum {string}
             */
            state: "NOT_REQUESTED" | "PENDING" | "READY" | "PARTIAL" | "FAILED" | "STALE";
            /** Total */
            total: number;
        };
        /** CommandReceipt */
        CommandReceipt: {
            command_id: components["schemas"]["Identity"];
            revision: components["schemas"]["PositiveRevision"];
            run_id?: components["schemas"]["Identity"] | null;
            setup_ref?: components["schemas"]["RunRef"] | null;
            /**
             * State
             * @enum {string}
             */
            state: "READY" | "ADMITTED";
        };
        /** ConnectionView */
        ConnectionView: {
            connection_id: components["schemas"]["Identity"];
            /** Credential Present */
            credential_present: boolean;
            /** Enabled */
            enabled: boolean;
            provider: components["schemas"]["Provider"];
            revision: components["schemas"]["PositiveRevision"];
        };
        /** @enum {string} */
        ConstraintKind: "READ_ONLY" | "EXCLUDE_FEATURE" | "REQUIRE_CRITERION";
        /** DashboardData */
        DashboardData: {
            active_run?: components["schemas"]["RunView"] | null;
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
             * @enum {string}
             */
            run_state: "NOT_RUN" | "RUNNING" | "PAUSING" | "PAUSED" | "HOLD" | "STOPPING" | "NEEDS_RECONCILIATION";
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
            run_id?: string | null;
            /**
             * Run State
             * @default NOT_RUN
             * @enum {string}
             */
            run_state: "NOT_RUN" | "RUNNING" | "PAUSING" | "PAUSED" | "HOLD" | "STOPPING" | "STOPPED" | "COMPLETED" | "LIMITED" | "NEEDS_RECONCILIATION";
            /**
             * Scope Revision Id
             * Format: uuid
             */
            scope_revision_id: string;
            /**
             * Stage
             * @default NOT_RUN
             * @enum {string}
             */
            stage: "NOT_RUN" | "INERT";
            /** Through Cursor */
            through_cursor?: number | null;
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
        Digest: string;
        /** DispatchUsage */
        DispatchUsage: {
            dispatch_id: components["schemas"]["Identity"];
            /** Reserved At */
            reserved_at: string | null;
            /** Sent At */
            sent_at: string | null;
            /** Settled At */
            settled_at: string | null;
            /**
             * State
             * @enum {string}
             */
            state: "RESERVED" | "SENT" | "SETTLED" | "RELEASED" | "UNKNOWN";
            usage: components["schemas"]["UsageRecord"] | null;
            usage_ref: components["schemas"]["RunRef"] | null;
        };
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
        /** EntryTestRequest */
        EntryTestRequest: {
            catalog_command_id: components["schemas"]["Identity"];
            /**
             * Consent
             * @constant
             */
            consent: true;
            entry_id: components["schemas"]["Identity"];
            expected_connection_revision: components["schemas"]["PositiveRevision"];
            expected_entry_revision: components["schemas"]["PositiveRevision"];
            /** Expected Generation */
            expected_generation: number;
            operation_id: components["schemas"]["Identity"];
        };
        /** EntryTestView */
        EntryTestView: {
            /**
             * Calls Limit
             * @default 1
             * @constant
             */
            calls_limit: 1;
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            /** Cost Observed */
            cost_observed?: string | null;
            /** Current */
            current: boolean;
            entry_id: components["schemas"]["Identity"];
            entry_revision: components["schemas"]["PositiveRevision"];
            /** Finish Reason */
            finish_reason?: string | null;
            /** Input Tokens */
            input_tokens?: number | null;
            metadata_command_id?: components["schemas"]["Identity"] | null;
            /**
             * Metadata State
             * @default NOT_REQUESTED
             * @enum {string}
             */
            metadata_state: "NOT_REQUESTED" | "PENDING" | "READY" | "FAILED";
            /** Observed Model */
            observed_model?: string | null;
            operation_id?: components["schemas"]["Identity"] | null;
            /**
             * Output State
             * @default ABSENT
             * @enum {string}
             */
            output_state: "COMPLETE" | "TRUNCATED" | "ABSENT";
            /** Output Tokens */
            output_tokens?: number | null;
            /** Provider Status */
            provider_status?: string | null;
            /** Reason */
            reason?: string | null;
            /** Reasoning Tokens */
            reasoning_tokens?: number | null;
            /** Requested Model */
            requested_model?: string | null;
            /** Requested Output Tokens */
            requested_output_tokens?: number | null;
            requested_provider?: components["schemas"]["Provider"] | null;
            /** Response Text */
            response_text?: string | null;
            result_state?: components["schemas"]["ResultState"] | null;
            /**
             * Schema Version
             * @default 2
             * @constant
             */
            schema_version: 2;
            selection_revision?: components["schemas"]["PositiveRevision"] | null;
            state?: components["schemas"]["State"] | null;
            state_revision?: components["schemas"]["PositiveRevision"] | null;
            /**
             * System Message
             * @default Respond only with OMNIS_MODEL_TEST_OK. Use no tools.
             */
            system_message: string;
            /**
             * Usage State
             * @default UNKNOWN
             * @enum {string}
             */
            usage_state: "KNOWN" | "PARTIAL" | "UNKNOWN";
            /**
             * User Message
             * @default This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.
             */
            user_message: string;
            /**
             * Wall Seconds
             * @default 300
             * @constant
             */
            wall_seconds: 300;
        };
        /**
         * ErrorCode
         * @enum {string}
         */
        ErrorCode: "INVALID_HOST" | "INVALID_ORIGIN" | "QUERY_NOT_ALLOWED" | "BODY_TOO_LARGE" | "UNAUTHENTICATED" | "CONTROL_UNAVAILABLE" | "INVALID_CSRF" | "CONTROL_TIMEOUT" | "PAIRING_DENIED" | "PAIRING_RATE_LIMITED" | "INVALID_INPUT" | "ENGAGEMENT_CONFLICT" | "COMMAND_CONFLICT" | "REVISION_CONFLICT" | "CONNECTION_UNAVAILABLE" | "REGISTRY_FULL" | "MODEL_NOT_REGISTERED" | "MODEL_IN_USE" | "CAPABILITIES_REQUIRED" | "OPERATION_ACTIVE" | "OPERATION_FINISHED" | "AUTHORITY_DENIED" | "ANSWER_DENIED" | "DATA_DENIED" | "REF_UNAVAILABLE" | "GENERATION_CONFLICT" | "CURSOR_DENIED" | "PROJECTION_LIMIT" | "CATALOG_LIST_LIMIT" | "NOT_FOUND" | "METHOD_NOT_ALLOWED" | "HTTP_ERROR" | "INTERNAL_ERROR" | "WEB_UNAVAILABLE";
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
        /** EventPage */
        EventPage: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Events */
            events: components["schemas"]["RunEvent"][];
            /** Has More */
            has_more: boolean;
            run_id: components["schemas"]["Identity"];
            through_cursor: components["schemas"]["Revision"];
        };
        /** ExactRef */
        ExactRef: {
            /** Digest */
            digest: string;
            /** Id */
            id: string;
            /** Kind */
            kind: string;
            /** Revision */
            revision: number;
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
        Identity: string;
        /** InboxConsumption */
        InboxConsumption: {
            consumer_attempt_id: components["schemas"]["Identity"] | null;
            decision_ref: components["schemas"]["RunRef"] | null;
            /** Held */
            held: boolean;
        };
        /** InputTokenDetails */
        InputTokenDetails: {
            cached_tokens?: components["schemas"]["TokenCount"] | null;
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
        /** KeySettingsView */
        KeySettingsView: {
            command_id: components["schemas"]["Identity"] | null;
            /** Connections */
            connections: components["schemas"]["ConnectionView"][];
            /**
             * Reachable
             * @default NOT_VERIFIED
             * @constant
             */
            reachable: "NOT_VERIFIED";
            /**
             * Schema Version
             * @default 2
             * @constant
             */
            schema_version: 2;
            /** Selection */
            selection: components["schemas"]["SelectionView"] | components["schemas"]["SelectionViewV2"] | null;
            /**
             * Vault Status
             * @enum {string}
             */
            vault_status: "LOCKED" | "UNLOCKED" | "UNCONFIGURED";
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
        /** ModelEntry */
        ModelEntry: {
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            entry_id: components["schemas"]["Identity"];
            /** Model */
            model: string;
            /** Output Tokens */
            output_tokens: number;
            revision: components["schemas"]["PositiveRevision"];
        };
        /** ModelRegistryView */
        ModelRegistryView: {
            after: components["schemas"]["Identity"] | null;
            command_id: components["schemas"]["Identity"] | null;
            /** Entries */
            entries: components["schemas"]["ModelEntry"][];
            next_after: components["schemas"]["Identity"] | null;
            registry_revision: components["schemas"]["Revision"];
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
            /** Total */
            total: number;
        };
        /** ModelSelection */
        ModelSelection: {
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            /** Model */
            model: string;
            /** Output Tokens */
            output_tokens: number;
        };
        /** ModelTestRequest */
        ModelTestRequest: {
            /**
             * Consent
             * @constant
             */
            consent: true;
            expected_selection_revision: components["schemas"]["PositiveRevision"];
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
            /** Cost Observed */
            cost_observed?: string | null;
            /** Finish Reason */
            finish_reason?: string | null;
            /** Input Tokens */
            input_tokens?: number | null;
            metadata_command_id?: components["schemas"]["Identity"] | null;
            /**
             * Metadata State
             * @default NOT_REQUESTED
             * @enum {string}
             */
            metadata_state: "NOT_REQUESTED" | "PENDING" | "READY" | "FAILED";
            /** Observed Model */
            observed_model?: string | null;
            operation_id?: components["schemas"]["Identity"] | null;
            /**
             * Output State
             * @default ABSENT
             * @enum {string}
             */
            output_state: "COMPLETE" | "TRUNCATED" | "ABSENT";
            /** Output Tokens */
            output_tokens?: number | null;
            /** Provider Status */
            provider_status?: string | null;
            /** Reason */
            reason?: string | null;
            /** Reasoning Tokens */
            reasoning_tokens?: number | null;
            /** Requested Model */
            requested_model?: string | null;
            /** Requested Output Tokens */
            requested_output_tokens?: number | null;
            requested_provider?: components["schemas"]["Provider"] | null;
            /** Response Text */
            response_text?: string | null;
            result_state?: components["schemas"]["ResultState"] | null;
            /**
             * Schema Version
             * @default 2
             * @constant
             */
            schema_version: 2;
            selection_revision?: components["schemas"]["PositiveRevision"] | null;
            state?: components["schemas"]["State"] | null;
            state_revision?: components["schemas"]["PositiveRevision"] | null;
            /**
             * System Message
             * @default Respond only with OMNIS_MODEL_TEST_OK. Use no tools.
             */
            system_message: string;
            /**
             * Usage State
             * @default UNKNOWN
             * @enum {string}
             */
            usage_state: "KNOWN" | "PARTIAL" | "UNKNOWN";
            /**
             * User Message
             * @default This is a synthetic local settings test. Reply with OMNIS_MODEL_TEST_OK.
             */
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
        /** OutputTokenDetails */
        OutputTokenDetails: {
            reasoning_tokens?: components["schemas"]["TokenCount"] | null;
        };
        /** PairingBody */
        PairingBody: {
            /** Code */
            code: string;
        };
        PositiveRevision: number;
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
        /** Preflight */
        Preflight: {
            command_id: components["schemas"]["Identity"];
            /**
             * Data Consent
             * @constant
             */
            data_consent: true;
            draft_ref: components["schemas"]["ExactRef"];
            engagement_id: components["schemas"]["Identity"];
            expected_generation: components["schemas"]["Revision"];
            publication_ref: components["schemas"]["ExactRef"];
            selection_revision: components["schemas"]["PositiveRevision"];
            /** Synthetic Context */
            synthetic_context: string;
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
             * @enum {integer}
             */
            schema_version: 1 | 2;
            /** Scope Revision Id */
            scope_revision_id?: null;
            /** Through Cursor */
            through_cursor?: null;
        };
        /** @enum {string} */
        Provider: "openrouter" | "orcarouter";
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
        /** Question */
        Question: {
            answer_ref?: components["schemas"]["RunRef"] | null;
            /** Cause */
            cause: string;
            command_id?: components["schemas"]["Identity"] | null;
            /**
             * Kind
             * @default CLARIFICATION
             * @constant
             */
            kind: "CLARIFICATION";
            question_id: components["schemas"]["Identity"];
            /** Refs */
            refs: components["schemas"]["RunRef"][];
            revision: components["schemas"]["PositiveRevision"];
            run_id: components["schemas"]["Identity"];
            /**
             * State
             * @enum {string}
             */
            state: "PENDING" | "ANSWER_ADMITTED" | "CONSUMED";
            task_id: components["schemas"]["Identity"];
            /** Text */
            text: string;
        };
        /**
         * ReadinessReason
         * @enum {string}
         */
        ReadinessReason: "DATABASE_UNAVAILABLE" | "SCHEMA_INCOMPATIBLE";
        /** Ref */
        Ref: {
            digest: components["schemas"]["Digest"];
            id: components["schemas"]["Identity"];
            instance_id: components["schemas"]["Identity"];
            /** Kind */
            kind: string;
            /**
             * Revision
             * @default 1
             * @constant
             */
            revision: 1;
        };
        /** RefreshCatalog */
        RefreshCatalog: {
            /**
             * Action
             * @constant
             */
            action: "refresh";
            command_id: components["schemas"]["Identity"];
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
        };
        /** RefreshRequest */
        RefreshRequest: {
            command_id: components["schemas"]["Identity"];
            expected_selection_revision: components["schemas"]["PositiveRevision"];
        };
        /** RemoveModel */
        RemoveModel: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "remove_model";
            command_id: components["schemas"]["Identity"];
            entry_id: components["schemas"]["Identity"];
            expected_registry_revision: components["schemas"]["Revision"];
            expected_revision: components["schemas"]["PositiveRevision"];
        };
        /** ReportedUsage */
        ReportedUsage: {
            cache_creation_input_tokens?: components["schemas"]["TokenCount"] | null;
            cache_read_input_tokens?: components["schemas"]["TokenCount"] | null;
            cached_tokens?: components["schemas"]["TokenCount"] | null;
            completion_tokens?: components["schemas"]["TokenCount"] | null;
            completion_tokens_details?: components["schemas"]["OutputTokenDetails"] | null;
            /** Cost */
            cost?: number | string | null;
            input_tokens?: components["schemas"]["TokenCount"] | null;
            output_tokens?: components["schemas"]["TokenCount"] | null;
            prompt_tokens?: components["schemas"]["TokenCount"] | null;
            prompt_tokens_details?: components["schemas"]["InputTokenDetails"] | null;
            reasoning_tokens?: components["schemas"]["TokenCount"] | null;
            total_tokens?: components["schemas"]["TokenCount"] | null;
        };
        /** ResultRecord */
        ResultRecord: {
            attempt_id: components["schemas"]["Identity"];
            /** Completion Kind */
            completion_kind?: ("direct" | "finish" | "error" | "cancel") | null;
            /** Consumed Refs */
            consumed_refs: components["schemas"]["RunRef"][];
            /** Gaps */
            gaps: string[];
            run_id: components["schemas"]["Identity"];
            /**
             * State
             * @enum {string}
             */
            state: "SUCCEEDED" | "INCONCLUSIVE" | "FAILED" | "CANCELLED";
            /** Summary */
            summary: string | null;
            task_id: components["schemas"]["Identity"];
        };
        /** @enum {string} */
        ResultState: "NOT_SENT" | "COMPLETED" | "INCOMPLETE" | "FAILED" | "UNKNOWN";
        Revision: number;
        /** RevisionPage */
        RevisionPage: {
            /** Has More */
            has_more: boolean;
            /** Items */
            items: components["schemas"]["EngagementView"][];
            /** Next Page */
            next_page: number | null;
        };
        /** RevokeConnection */
        RevokeConnection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "revoke_connection";
            command_id: components["schemas"]["Identity"];
            connection_id: components["schemas"]["Identity"];
            expected_revision: components["schemas"]["PositiveRevision"];
        };
        /** RoleUsage */
        RoleUsage: {
            /** Configured Model */
            configured_model: string;
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            /**
             * Role
             * @enum {string}
             */
            role: "BRAIN" | "RECON";
            totals: components["schemas"]["UsageTotals"];
        };
        /** RunCommand */
        RunCommand: {
            /**
             * Action
             * @enum {string}
             */
            action: "pause" | "stop" | "resume" | "answer";
            /** Answer */
            answer?: string | null;
            command_id: components["schemas"]["Identity"];
            expected_generation: components["schemas"]["Revision"];
            expected_revision: components["schemas"]["PositiveRevision"];
            question_id?: components["schemas"]["Identity"] | null;
            run_id: components["schemas"]["Identity"];
        };
        /** RunEvent */
        RunEvent: {
            attempt_id: components["schemas"]["Identity"] | null;
            /** Call Id */
            call_id: string | null;
            /**
             * Created At
             * Format: date-time
             */
            created_at: string;
            event_id: components["schemas"]["Identity"];
            /**
             * Kind
             * @enum {string}
             */
            kind: "started" | "decision" | "tool_called" | "tool_result" | "result" | "control" | "question" | "answer";
            /** Refs */
            refs: components["schemas"]["RunRef"][];
            run_id: components["schemas"]["Identity"];
            sequence: components["schemas"]["PositiveRevision"];
            /** Summary */
            summary: string;
            task_id: components["schemas"]["Identity"] | null;
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
        RunRef: components["schemas"]["Ref"];
        /** RunSummary */
        RunSummary: {
            /**
             * As Of
             * Format: date-time
             */
            as_of: string;
            /** Attempts */
            attempts: components["schemas"]["Attempt"][];
            /** Has More */
            has_more: boolean;
            /** Owner Live */
            owner_live: boolean;
            /** Phase Active */
            phase_active: boolean;
            question: components["schemas"]["Question"] | null;
            run: components["schemas"]["RunView"];
            usage: components["schemas"]["UsageSummary"];
        };
        /** RunView */
        RunView: {
            active_attempt_id?: components["schemas"]["Identity"] | null;
            engagement_id: components["schemas"]["Identity"];
            fence: components["schemas"]["PositiveRevision"];
            generation: components["schemas"]["Revision"];
            instance_id: components["schemas"]["Identity"];
            owner_epoch: components["schemas"]["PositiveRevision"];
            owner_id: components["schemas"]["Identity"];
            question_id?: components["schemas"]["Identity"] | null;
            /** Reason */
            reason?: string | null;
            revision: components["schemas"]["PositiveRevision"];
            run_id: components["schemas"]["Identity"];
            /**
             * Schema Version
             * @default 1
             * @constant
             */
            schema_version: 1;
            setup_ref: components["schemas"]["RunRef"];
            /**
             * Stagnation
             * @default 0
             */
            stagnation: number;
            /**
             * State
             * @enum {string}
             */
            state: "RUNNING" | "PAUSING" | "PAUSED" | "HOLD" | "STOPPING" | "STOPPED" | "COMPLETED" | "LIMITED" | "NEEDS_RECONCILIATION";
            /** @default 0 */
            through_cursor: components["schemas"]["Revision"];
        };
        /** SaveConnection */
        SaveConnection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "save_connection";
            command_id: components["schemas"]["Identity"];
            connection_id: components["schemas"]["Identity"];
            expected_revision: components["schemas"]["Revision"];
            provider: components["schemas"]["Provider"];
            /**
             * Secret
             * Format: password
             */
            secret: string;
        };
        /** SaveModel */
        SaveModel: {
            entry_id: components["schemas"]["Identity"];
            expected_revision: components["schemas"]["Revision"];
            /** Model */
            model: string;
            /** Output Tokens */
            output_tokens: number;
        };
        /** SaveModels */
        SaveModels: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "save_models";
            command_id: components["schemas"]["Identity"];
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            expected_registry_revision: components["schemas"]["Revision"];
            /** Models */
            models: components["schemas"]["SaveModel"][];
        };
        /** SaveSelection */
        SaveSelection: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "save_selection";
            brain: components["schemas"]["ModelSelection"] | null;
            command_id: components["schemas"]["Identity"];
            default: components["schemas"]["ModelSelection"];
            expected_revision: components["schemas"]["Revision"];
            investigator: components["schemas"]["ModelSelection"] | null;
            validator: components["schemas"]["ModelSelection"] | null;
        };
        /** SaveSelectionV2 */
        SaveSelectionV2: {
            /**
             * @description discriminator enum property added by openapi-typescript
             * @enum {string}
             */
            action: "save_selection_v2";
            brain: components["schemas"]["ModelSelection"] | null;
            command_id: components["schemas"]["Identity"];
            default: components["schemas"]["ModelSelection"];
            expected_revision: components["schemas"]["Revision"];
            investigator: components["schemas"]["ModelSelection"] | null;
            recon: components["schemas"]["ModelSelection"] | null;
            validator: components["schemas"]["ModelSelection"] | null;
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
        /** SearchCatalog */
        SearchCatalog: {
            /**
             * Action
             * @constant
             */
            action: "search";
            catalog_command_id?: components["schemas"]["Identity"] | null;
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            /**
             * Offset
             * @default 0
             */
            offset: number;
            /**
             * Query
             * @default
             */
            query: string;
        };
        /** SelectionView */
        SelectionView: {
            brain: components["schemas"]["ModelSelection"] | null;
            default: components["schemas"]["ModelSelection"];
            investigator: components["schemas"]["ModelSelection"] | null;
            revision: components["schemas"]["PositiveRevision"];
            selection_id: components["schemas"]["Identity"];
            validator: components["schemas"]["ModelSelection"] | null;
        };
        /** SelectionViewV2 */
        SelectionViewV2: {
            brain: components["schemas"]["ModelSelection"] | null;
            default: components["schemas"]["ModelSelection"];
            investigator: components["schemas"]["ModelSelection"] | null;
            recon: components["schemas"]["ModelSelection"] | null;
            revision: components["schemas"]["PositiveRevision"];
            /**
             * Schema Version
             * @constant
             */
            schema_version: 2;
            selection_id: components["schemas"]["Identity"];
            validator: components["schemas"]["ModelSelection"] | null;
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
        /** StartRun */
        StartRun: {
            command_id: components["schemas"]["Identity"];
            expected_generation: components["schemas"]["Revision"];
            /**
             * Expected Revision
             * @constant
             */
            expected_revision: 1;
            setup_ref: components["schemas"]["RunRef"];
        };
        /** @enum {string} */
        State: "PENDING" | "RUNNING" | "STOPPING" | "FINISHED" | "NEEDS_RECONCILIATION";
        TokenCount: number;
        /** UsageMeasures */
        UsageMeasures: {
            cache_creation_tokens?: components["schemas"]["TokenCount"] | null;
            cached_tokens?: components["schemas"]["TokenCount"] | null;
            /** Cost Observed */
            cost_observed?: string | null;
            input_tokens?: components["schemas"]["TokenCount"] | null;
            output_tokens?: components["schemas"]["TokenCount"] | null;
            reasoning_tokens?: components["schemas"]["TokenCount"] | null;
            total_tokens?: components["schemas"]["TokenCount"] | null;
        };
        /** UsageRecord */
        UsageRecord: {
            attempt_id: components["schemas"]["Identity"];
            /** Configured Model */
            configured_model: string;
            connection_id: components["schemas"]["Identity"];
            connection_revision: components["schemas"]["PositiveRevision"];
            dispatch_id: components["schemas"]["Identity"];
            instance_id: components["schemas"]["Identity"];
            measures: components["schemas"]["UsageMeasures"];
            /**
             * Observed At
             * Format: date-time
             */
            observed_at: string;
            /** Observed Model */
            observed_model?: string | null;
            reported: components["schemas"]["ReportedUsage"];
            /**
             * Role
             * @enum {string}
             */
            role: "BRAIN" | "RECON";
            run_id: components["schemas"]["Identity"];
            task_id: components["schemas"]["Identity"];
        };
        /** UsageSubtotal */
        UsageSubtotal: {
            observed_dispatches: components["schemas"]["Revision"];
            /**
             * State
             * @enum {string}
             */
            state: "OBSERVED" | "PARTIAL" | "UNKNOWN";
            /** Value */
            value: string | null;
        };
        /** UsageSummary */
        UsageSummary: {
            /**
             * Accounting Policy
             * @default MONITOR
             * @constant
             */
            accounting_policy: "MONITOR";
            /** Roles */
            roles: components["schemas"]["RoleUsage"][];
            /**
             * Scope
             * @enum {string}
             */
            scope: "RUN" | "ATTEMPT";
            totals: components["schemas"]["UsageTotals"];
        };
        /** UsageTotals */
        UsageTotals: {
            cache_creation_tokens: components["schemas"]["UsageSubtotal"];
            cached_tokens: components["schemas"]["UsageSubtotal"];
            cost_observed: components["schemas"]["UsageSubtotal"];
            dispatches: components["schemas"]["Revision"];
            input_tokens: components["schemas"]["UsageSubtotal"];
            output_tokens: components["schemas"]["UsageSubtotal"];
            reasoning_tokens: components["schemas"]["UsageSubtotal"];
            total_tokens: components["schemas"]["UsageSubtotal"];
            unobserved_dispatches: components["schemas"]["Revision"];
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
    engagement_run_api_v1_engagements__engagement_id__run_get: {
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
                    "application/json": components["schemas"]["RunView"] | null;
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
    preflight_api_v1_engagements__engagement_id__run_preflight_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                engagement_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["Preflight"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
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
            202: {
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
    refresh_capabilities_api_v1_model_test_capabilities_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
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
            /** @description Conflict */
            409: {
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
    read_capabilities_api_v1_model_test_capabilities__command_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command_id: string;
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
    start_entry_test_api_v1_model_test_entries_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["EntryTestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EntryTestView"];
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
    read_latest_entry_test_api_v1_model_test_entries_latest__entry_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                entry_id: string;
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
                    "application/json": components["schemas"]["EntryTestView"];
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
    read_entry_test_api_v1_model_test_entries__operation_id__get: {
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
                    "application/json": components["schemas"]["EntryTestView"];
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
    cancel_entry_test_api_v1_model_test_entries__operation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CancelTestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["EntryTestView"];
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
    read_operation_api_v1_model_test__operation_id__get: {
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
    cancel_operation_api_v1_model_test__operation_id__cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                operation_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CancelTestRequest"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
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
            /** @description Conflict */
            409: {
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
    start_api_v1_runs_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["StartRun"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
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
    active_api_v1_runs_active_get: {
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
                    "application/json": components["schemas"]["RunView"] | null;
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
    command_read_api_v1_runs_commands__command_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command_id: string;
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
                    "application/json": components["schemas"]["CommandReceipt"];
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
    publications_api_v1_runs_publications_get: {
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
                    "application/json": components["schemas"]["ExactRef"][];
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
            /** @description Conflict */
            409: {
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
    attempt_api_v1_runs__run_id__attempts__attempt_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
                attempt_id: string;
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
                    "application/json": components["schemas"]["AttemptInspection"];
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
    command_api_v1_runs__run_id__commands_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: string;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunCommand"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CommandReceipt"];
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
    events_api_v1_runs__run_id__events_get: {
        parameters: {
            query?: {
                after?: string | null;
                limit?: number;
            };
            header?: never;
            path: {
                run_id: string;
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
                    "application/json": components["schemas"]["EventPage"];
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
    summary_api_v1_runs__run_id__summary_get: {
        parameters: {
            query?: {
                limit?: number;
            };
            header?: never;
            path: {
                run_id: string;
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
                    "application/json": components["schemas"]["RunSummary"];
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
    read_models_api_v1_settings_models_get: {
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
                    "application/json": components["schemas"]["ModelRegistryView"];
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
    save_models_api_v1_settings_models_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveModels"] | components["schemas"]["RemoveModel"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ModelRegistryView"];
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
    read_command_api_v1_settings_models_commands__command_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command_id: string;
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
                    "application/json": components["schemas"]["ModelRegistryView"];
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
    read_page_api_v1_settings_models_pages__registry_revision___after__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                registry_revision: string;
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
                    "application/json": components["schemas"]["ModelRegistryView"];
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
    cancel_catalog_api_v1_settings_provider_catalog_cancel_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CancelCatalog"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogView"];
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
    refresh_catalog_api_v1_settings_provider_catalog_refresh_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RefreshCatalog"];
            };
        };
        responses: {
            /** @description Successful Response */
            202: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogView"];
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
            /** @description Conflict */
            409: {
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
    search_catalog_api_v1_settings_provider_catalog_search_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SearchCatalog"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CatalogView"];
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
    read_settings_api_v1_settings_providers_get: {
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
                    "application/json": components["schemas"]["KeySettingsView"];
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
    save_settings_api_v1_settings_providers_put: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SaveConnection"] | components["schemas"]["RevokeConnection"] | components["schemas"]["SaveSelection"] | components["schemas"]["SaveSelectionV2"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["KeySettingsView"];
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
    read_command_api_v1_settings_providers_commands__command_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                command_id: string;
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
                    "application/json": components["schemas"]["KeySettingsView"];
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
