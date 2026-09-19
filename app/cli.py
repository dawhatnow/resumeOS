import typer

from app.importing.profile_builder import ProfileImporter
from app.models import Profile
from app.paths import ResumePathResolver
from app.store import ProfileStore

app = typer.Typer()


@app.command()
def new():
    typer.echo("Creating a new resume...")

    raw_path = typer.prompt("Enter the path to your master resume (PDF)")
    path = ResumePathResolver().resolve(raw_path)

    try:
        profile = ProfileImporter().import_pdf(path)
    except (FileNotFoundError, ValueError) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    _print_profile(profile)

    saved_path = ProfileStore().save(profile)
    typer.echo(f"\nSaved profile to {saved_path}")


def _print_profile(profile: Profile) -> None:
    typer.echo(f"Name: {profile.personal.name}")
    typer.echo(f"Email: {profile.personal.email}")
    typer.echo(f"Phone: {profile.personal.phone}")
    typer.echo(f"Links: {', '.join(profile.personal.links) or 'none found'}")
    typer.echo(f"Summary: {profile.summary or 'none found'}")

    typer.echo(f"\nExperience ({len(profile.experiences)}):")
    for item in profile.experiences:
        typer.echo(f"  [{item.id}] {item.title} @ {item.org} ({item.dates})")
        for bullet in item.bullets:
            typer.echo(f"    - {bullet.text}")

    typer.echo(f"\nProjects ({len(profile.projects)}):")
    for item in profile.projects:
        tech = f" [{', '.join(item.tech)}]" if item.tech else ""
        typer.echo(f"  [{item.id}] {item.title}{tech}")
        for bullet in item.bullets:
            typer.echo(f"    - {bullet.text}")

    typer.echo(f"\nEducation ({len(profile.education)}):")
    for edu in profile.education:
        typer.echo(f"  {edu.school} — {edu.degree} ({edu.dates})")

    typer.echo(f"\nSkills: {', '.join(profile.skills) or 'none found'}")


if __name__ == "__main__":
    app()
