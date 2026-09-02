---
name: unreal_engine
description: Unreal Engine 5 development, project inspection, C++ reflection macros, log analysis, and build tools.
triggers:
  - unreal
  - uproject
  - blueprint
  - uat
  - ubt
  - c++ reflection
  - ue5
tools:
  - unreal.detect_project
  - unreal.read_logs
  - unreal.build
category: gamedev
---

# Unreal Engine 5 (UE5) Development & Diagnostics

You are equipped with specialized knowledge and tools for Unreal Engine 5 development, C++ gameplay architecture, project inspection, log diagnostics, and build execution.

## 1. Project Directory Anatomy
Unreal Engine projects follow a strict directory convention centered around the primary descriptor file:
- **`{ProjectName}.uproject`**: JSON manifest defining engine version association, gameplay modules, and enabled plugins.
- **`Source/`**: Native C++ source code.
  - `{ProjectName}.Target.cs`: Standalone game build target definition.
  - `{ProjectName}Editor.Target.cs`: Editor build target definition.
  - `{ModuleName}/`: C++ Module directory.
    - `{ModuleName}.Build.cs`: Module dependency rules (`PublicDependencyModuleNames`, `PrivateDependencyModuleNames`).
    - `Public/` & `Private/`: Header and implementation files.
- **`Plugins/`**: Project-specific or third-party plugins with isolated `Source/` and `Content/`.
- **`Config/`**: Engine, Game, Input, and Editor configuration `.ini` files (`DefaultEngine.ini`, `DefaultGame.ini`).
- **`Content/`**: Binary uasset/umap assets (Textures, Blueprints, Materials, Levels).
- **`Saved/Logs/`**: Runtime, cooking, and editor execution logs (`{ProjectName}.log`).
- **`Binaries/` & `Intermediate/`**: Compiled dynamic libraries (`.dll`/`.dylib`) and generated reflection headers (`.generated.h`).

## 2. C++ Reflection & Macro Rules
All Unreal Engine reflected types must adhere to strict macro patterns:
- **Include Order**: Every reflected header must include its generated header as the LAST include: `#include "MyClass.generated.h"`.
- **UCLASS**:
  ```cpp
  UCLASS(Blueprintable, ClassGroup=(Custom), meta=(BlueprintSpawnableComponent))
  class MYPROJECT_API UMyActorComponent : public UActorComponent
  {
      GENERATED_BODY()
  public:
      UMyActorComponent();
  };
  ```
- **UPROPERTY**:
  ```cpp
  UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Gameplay|Stats", meta = (ClampMin = "0.0"))
  float Health = 100.0f;
  ```
- **UFUNCTION**:
  ```cpp
  UFUNCTION(BlueprintCallable, Category = "Gameplay|Combat")
  void TakeDamage(float Amount);
  ```

## 3. Build & Automation Tools
- **UnrealBuildTool (UBT)**: Compiles C++ modules and targets (`UBT.exe {ProjectName}Editor Win64 Development "{ProjectPath}"`).
- **Unreal Automation Tool (UAT)**: Automates cooking, packaging, and testing (`RunUAT.bat BuildCookRun -project="{ProjectPath}" ...`).

## 4. Available Tools
- `unreal.detect_project`: Scans for `.uproject` in workspace and returns engine version, modules, and enabled plugins.
- `unreal.read_logs`: Tails recent output logs from `Saved/Logs/{ProjectName}.log` to diagnose compilation, crash, or cooking errors.
- `unreal.build`: Dispatches automated build commands through the sandbox manager.
