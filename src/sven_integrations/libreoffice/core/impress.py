"""Impress presentation operations — in-memory model for LibreOffice Impress."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ImpressImage:
    """An image placed on a slide."""

    image_path: str
    x_mm: float
    y_mm: float
    width_mm: float
    height_mm: float


@dataclass
class ImpressSlide:
    """A single slide in a presentation."""

    index: int
    title: str = ""
    content: str = ""
    layout: int = 1
    background_color: str = "#ffffff"
    images: list[ImpressImage] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "content": self.content,
            "layout": self.layout,
            "background_color": self.background_color,
            "images": [
                {
                    "image_path": img.image_path,
                    "x_mm": img.x_mm,
                    "y_mm": img.y_mm,
                    "width_mm": img.width_mm,
                    "height_mm": img.height_mm,
                }
                for img in self.images
            ],
        }


@dataclass
class ImpressPresentation:
    """In-memory model for a LibreOffice Impress presentation."""

    title: str
    slides: list[ImpressSlide] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "slides": [s.to_dict() for s in self.slides],
        }


def create_presentation(title: str) -> ImpressPresentation:
    """Create a new presentation with a single blank title slide."""
    pres = ImpressPresentation(title=title)
    pres.slides.append(ImpressSlide(index=0, title=title, layout=0))
    return pres


def add_slide(pres: ImpressPresentation, layout: int = 1) -> ImpressSlide:
    """Append a new blank slide with *layout* and return it."""
    idx = len(pres.slides)
    slide = ImpressSlide(index=idx, layout=layout)
    pres.slides.append(slide)
    return slide


def _get_slide(pres: ImpressPresentation, slide_idx: int) -> ImpressSlide:
    if not (0 <= slide_idx < len(pres.slides)):
        raise IndexError(f"Slide index {slide_idx} out of range (0–{len(pres.slides) - 1})")
    return pres.slides[slide_idx]


def set_slide_title(pres: ImpressPresentation, slide_idx: int, title: str) -> None:
    """Set the title text of the slide at *slide_idx*."""
    _get_slide(pres, slide_idx).title = title


def set_slide_content(pres: ImpressPresentation, slide_idx: int, content_text: str) -> None:
    """Set the body content text of the slide at *slide_idx*."""
    _get_slide(pres, slide_idx).content = content_text


def add_image(
    pres: ImpressPresentation,
    slide_idx: int,
    image_path: str,
    x_mm: float,
    y_mm: float,
    width_mm: float,
    height_mm: float,
) -> None:
    """Place an image on the slide at *slide_idx*."""
    slide = _get_slide(pres, slide_idx)
    slide.images.append(
        ImpressImage(
            image_path=image_path,
            x_mm=x_mm,
            y_mm=y_mm,
            width_mm=width_mm,
            height_mm=height_mm,
        )
    )


def set_slide_background(
    pres: ImpressPresentation, slide_idx: int, color_hex: str
) -> None:
    """Set the background fill colour of the slide at *slide_idx*.

    *color_hex* should be a CSS hex string such as ``"#1a2b3c"``.
    """
    _get_slide(pres, slide_idx).background_color = color_hex


def duplicate_slide(pres: ImpressPresentation, slide_idx: int) -> ImpressSlide:
    """Duplicate the slide at *slide_idx* and append the copy at the end."""
    import copy

    original = _get_slide(pres, slide_idx)
    new_slide = copy.deepcopy(original)
    new_slide.index = len(pres.slides)
    pres.slides.append(new_slide)
    return new_slide


def delete_slide(pres: ImpressPresentation, slide_idx: int) -> ImpressSlide:
    """Remove the slide at *slide_idx* and return it."""
    slide = _get_slide(pres, slide_idx)
    pres.slides.pop(slide_idx)
    for i, s in enumerate(pres.slides):
        s.index = i
    return slide


def get_slide_count(pres: ImpressPresentation) -> int:
    """Return the total number of slides."""
    return len(pres.slides)
