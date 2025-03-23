# src/utils/route_handlers.py
import re

from firebase_functions import https_fn

from .response_utils import error_response


class Route:
    """Represents a route in the application.

    This class helps define routes with handlers, path patterns,
    and allowed HTTP methods.
    """

    def __init__(self, path_pattern, handler_func, methods=None, cors=None):
        """Initialize a route.

        Args:
            path_pattern (str): URL path pattern with parameter placeholders
                                (e.g., '/api/rulesets/{ruleset_id}/rules')
            handler_func (callable): Handler function for this route
            methods (list, optional): Allowed HTTP methods (default: ['GET'])
            cors (object, optional): CORS configuration for the route
        """
        self.path_pattern = path_pattern
        self.handler_func = handler_func
        self.methods = methods or ["GET"]
        self.cors = cors

        # Extract parameter names from path pattern
        self.param_names = self._extract_param_names(path_pattern)

        # Generate regex pattern for matching paths
        self.path_regex = self._create_path_regex(path_pattern)

    def matches(self, path):
        """Check if a path matches this route's pattern.

        Args:
            path (str): URL path to check

        Returns:
            bool: True if the path matches this route's pattern
        """
        return bool(self.path_regex.match(path))

    def extract_params(self, path):
        """Extract parameters from a path based on this route's pattern.

        Args:
            path (str): URL path to extract parameters from

        Returns:
            dict: Extracted parameters or empty dict if no match
        """
        match = self.path_regex.match(path)
        if not match:
            return {}

        return match.groupdict()

    def create_function(self, function_prefix=""):
        """Create a Firebase Function for this route.

        Args:
            function_prefix (str, optional): Prefix for the function name

        Returns:
            function: Firebase Function handler
        """
        # Generate a function name based on the handler function name
        function_name = f"{function_prefix}_{self.handler_func.__name__}_fn"

        # Define the Firebase Function handler
        @https_fn.on_request(cors=self.cors)
        def handler(request: https_fn.Request) -> https_fn.Response:
            # Check if the HTTP method is allowed
            if request.method not in self.methods:
                return error_response(
                    f"Method {request.method} not allowed",
                    status=405,
                    format=(
                        "json"
                        if "application/json" in (request.headers.get("Accept") or "")
                        else "html"
                    ),
                )

            # Extract parameters from the path
            path_params = self.extract_params(request.path)

            # Call the handler function with request and path parameters
            return self.handler_func(request, **path_params)

        # Set the function name
        handler.__name__ = function_name
        return handler

    def _extract_param_names(self, path_pattern):
        """Extract parameter names from a path pattern.

        Args:
            path_pattern (str): Path pattern with parameter placeholders

        Returns:
            list: List of parameter names
        """
        matches = re.findall(r"{([^{}]+)}", path_pattern)
        return matches

    def _create_path_regex(self, path_pattern):
        """Create a regex pattern for matching paths against this route's pattern.

        Args:
            path_pattern (str): Path pattern with parameter placeholders

        Returns:
            re.Pattern: Compiled regex pattern
        """
        # Replace parameter placeholders with named capture groups
        regex_pattern = path_pattern
        for param_name in self.param_names:
            placeholder = f"{{{param_name}}}"
            regex_pattern = regex_pattern.replace(
                placeholder, f"(?P<{param_name}>[^/]+)"
            )

        # Anchor the pattern to the start/end of the path
        regex_pattern = f"^{regex_pattern}$"

        return re.compile(regex_pattern)


class Router:
    """Router for managing application routes.

    This class provides a central registry for all application routes
    and handles route matching and function generation.
    """

    def __init__(self, default_cors=None):
        """Initialize the router.

        Args:
            default_cors (object, optional): Default CORS configuration for routes
        """
        self.routes = []
        self.default_cors = default_cors

    def add_route(self, path_pattern, handler_func, methods=None, cors=None):
        """Add a route to the router.

        Args:
            path_pattern (str): URL path pattern with parameter placeholders
            handler_func (callable): Handler function for this route
            methods (list, optional): Allowed HTTP methods
            cors (object, optional): CORS configuration (uses default if None)

        Returns:
            Route: The created route
        """
        route = Route(
            path_pattern, handler_func, methods=methods, cors=cors or self.default_cors
        )
        self.routes.append(route)
        return route

    def match_route(self, path):
        """Find a route that matches a path.

        Args:
            path (str): URL path to match

        Returns:
            tuple: (Route, dict) - Matching route and extracted parameters,
                   or (None, {}) if no match
        """
        for route in self.routes:
            if route.matches(path):
                params = route.extract_params(path)
                return route, params

        return None, {}

    def generate_functions(self, function_prefix=""):
        """Generate Firebase Functions for all routes.

        Args:
            function_prefix (str, optional): Prefix for function names

        Returns:
            dict: Dictionary of function name to Firebase Function
        """
        functions = {}

        for route in self.routes:
            func = route.create_function(function_prefix)
            func_name = func.__name__
            functions[func_name] = func

        return functions


def create_application_router(cors_config):
    """Create the application router with all routes.

    Args:
        cors_config: CORS configuration for routes

    Returns:
        Router: Configured router with all application routes
    """
    from ..auth.auth_routes import exchange_token, get_user, init_speckle_auth
    from ..projects.project_routes import (
        get_new_ruleset_form,
        get_project_with_rulesets,
        get_user_projects_view,
    )
    from ..rules.rule_routes import (
        create_rule_handler,
        delete_rule_handler,
        get_condition_row,
        get_edit_rule_form,
        get_new_rule_form,
        get_rules,
        update_rule_handler,
    )
    from ..rulesets.ruleset_export import export_ruleset_as_tsv
    from ..rulesets.ruleset_routes import (
        create_new_ruleset,
        delete_ruleset_handler,
        get_ruleset_edit_form,
        toggle_ruleset_sharing_handler,
        update_ruleset_info,
    )
    from ..rulesets.ruleset_sharing import get_shared_ruleset_view

    router = Router(default_cors=cors_config)

    # Authentication routes
    router.add_route("/api/auth/init", init_speckle_auth, methods=["GET"])
    router.add_route("/api/auth/token", exchange_token, methods=["POST"])
    router.add_route("/api/auth/users", get_user, methods=["GET", "POST"])

    # Project routes
    router.add_route("/api/projects", get_user_projects_view, methods=["GET"])
    router.add_route(
        "/api/projects/{project_id}", get_project_with_rulesets, methods=["GET"]
    )
    router.add_route("/api/rulesets/new", get_new_ruleset_form, methods=["GET"])

    # Ruleset routes
    router.add_route("/api/rulesets", create_new_ruleset, methods=["POST"])
    router.add_route(
        "/api/rulesets/{ruleset_id}", get_ruleset_edit_form, methods=["GET"]
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/delete", delete_ruleset_handler, methods=["DELETE"]
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/edit", get_ruleset_edit_form, methods=["GET"]
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/share",
        toggle_ruleset_sharing_handler,
        methods=["PATCH"],
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/export", export_ruleset_as_tsv, methods=["GET"]
    )

    # Rule routes
    router.add_route("/api/rulesets/{ruleset_id}/rules", get_rules, methods=["GET"])
    router.add_route(
        "/api/rulesets/{ruleset_id}/rules", create_rule_handler, methods=["POST"]
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/rules/new", get_new_rule_form, methods=["GET"]
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/rules/{rule_id}/edit",
        get_edit_rule_form,
        methods=["GET"],
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/rules/{rule_id}",
        update_rule_handler,
        methods=["PUT"],
    )
    router.add_route(
        "/api/rulesets/{ruleset_id}/rules/{rule_id}",
        delete_rule_handler,
        methods=["DELETE"],
    )

    # Utility routes
    router.add_route("/api/rule/condition", get_condition_row, methods=["GET"])

    # Shared ruleset routes
    router.add_route("/shared/{ruleset_id}", get_shared_ruleset_view, methods=["GET"])

    return router
