"""Blender subprocess bridge.

Runs Blender in background mode via::

    blender [blend_file] --background --python-expr <script>

Python expressions are assembled by the caller; this module only handles
process management and error detection.
"""

from __future__ import annotations

import subprocess


class BlenderError(RuntimeError):
    """Raised when the Blender process exits with a non-zero return code."""


class BlenderBackend:
    """Thin wrapper around Blender's ``--background --python-expr`` interface.

    Parameters
    ----------
    executable:
        Path (or name on ``$PATH``) of the Blender binary.
    timeout:
        Maximum seconds to wait before raising
        :class:`subprocess.TimeoutExpired`.
    """

    def __init__(
        self,
        executable: str = "blender",
        timeout: float = 300.0,
    ) -> None:
        self.executable = executable
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Script construction helpers

    @staticmethod
    def build_python_expr(commands: list[str]) -> str:
        """Join a list of Python statements into a single ``--python-expr`` string.

        Statements are joined with ``; `` so they run sequentially in one
        Blender Python evaluation.

        Example::

            build_python_expr([
                "import bpy",
                "bpy.ops.mesh.primitive_cube_add()",
                "bpy.ops.wm.save_as_mainfile(filepath='/tmp/out.blend')",
            ])
        """
        return "; ".join(commands)

    # ------------------------------------------------------------------
    # Core execution

    def run_blender(
        self,
        script: str,
        blend_file: str | None = None,
    ) -> str:
        """Execute *script* inside Blender and return stdout.

        Parameters
        ----------
        script:
            A Python expression (or several joined with ``;``) to pass via
            ``--python-expr``.
        blend_file:
            Optional ``.blend`` file to open before running the script.

        Raises
        ------
        BlenderError
            If Blender exits with a non-zero code.
        """
        cmd: list[str] = [self.executable]
        if blend_file:
            cmd.append(blend_file)
        cmd.extend(["--background", "--python-expr", script])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
        except FileNotFoundError as exc:
            raise BlenderError(
                f"Blender binary not found: {self.executable!r}. "
                "Install Blender and ensure it is on PATH, or set BLENDER_BIN env variable."
            ) from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip()
            raise BlenderError(
                f"Blender exited {result.returncode}: {detail}"
            )
        return result.stdout

    # ------------------------------------------------------------------
    # Higher-level operations

    def render(
        self,
        output_path: str,
        frame: int | None = None,
        blend_file: str | None = None,
    ) -> str:
        """Render a single frame (or the active frame) to *output_path*.

        The output file format is determined by the scene's render settings
        already stored in the .blend file.
        """
        escaped = output_path.replace("\\", "\\\\").replace('"', '\\"')
        statements = [
            "import bpy",
            f'bpy.context.scene.render.filepath = "{escaped}"',
        ]
        if frame is not None:
            statements.append(f"bpy.context.scene.frame_set({frame})")
        statements.append("bpy.ops.render.render(write_still=True)")
        script = self.build_python_expr(statements)
        return self.run_blender(script, blend_file=blend_file)
